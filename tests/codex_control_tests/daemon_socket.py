"""Independent, local-only Codex WebSocket test double. Never starts Codex."""
import base64
import hashlib
import json
from pathlib import Path
import socket
import socketserver
import struct
import threading
import time
import zipfile


_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def recv_exact(sock, count):
    value = b""
    while len(value) < count:
        chunk = sock.recv(count-len(value))
        if not chunk:
            raise EOFError()
        value += chunk
    return value


def receive(sock):
    a,b = recv_exact(sock,2)
    length = b & 0x7f
    if length == 126: length=struct.unpack('!H',recv_exact(sock,2))[0]
    if length == 127: length=struct.unpack('!Q',recv_exact(sock,8))[0]
    mask = recv_exact(sock,4) if b & 128 else b'\0'*4
    data = recv_exact(sock,length)
    return a & 15, bytes(v^mask[i%4] for i,v in enumerate(data)) if b & 128 else data, bool(a & 128), bool(b & 128)


def send_frame(sock, body, opcode=1, fin=True):
    head = bytearray([(0x80 if fin else 0) | opcode])
    size = len(body)
    if size < 126: head.append(size)
    elif size <= 65535:
        head.append(126); head.extend(struct.pack('!H',size))
    else:
        head.append(127); head.extend(struct.pack('!Q',size))
    sock.sendall(bytes(head)+body)


class FakeServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, path, home, dev):
        self.home, self.dev = Path(home), Path(dev)
        self.history = {}
        self.requests = []
        super().__init__(str(path), FakeHandler)


class FakeHandler(socketserver.BaseRequestHandler):
    def settings(self):
        return json.loads((self.server.home/'test.json').read_text())

    def respond(self, doc):
        payload = json.dumps(doc).encode()
        options = self.settings()
        if options.get('frame_ping'):
            send_frame(self.request, b'hello',opcode=9)
        if options.get('frame_close'):
            send_frame(self.request, b'',opcode=8); return
        if options.get('frame_binary'):
            send_frame(self.request,payload,opcode=2); return
        if options.get('frame_masked'):
            self.request.sendall(bytes([0x81, 0x80 | 1, 0,0,0,0]) + b'X'); return
        if options.get('frame_oversized'):
            self.request.sendall(bytes([0x81,127]) + struct.pack('!Q', 2**30)); return
        if options.get('fragment'):
            send_frame(self.request,payload[:len(payload)//2],fin=False)
            if options.get('frame_ping'):
                send_frame(self.request,b'between',opcode=9)
            send_frame(self.request,payload[len(payload)//2:],opcode=0)
        else:
            send_frame(self.request,payload)

    def reply(self, ident, result):
        self.respond({'id':ident,'result':result})

    def handle(self):
        try:
            self.request.settimeout(20)
            headers = b''
            while not headers.endswith(b'\r\n\r\n') and len(headers)<8192:
                headers += recv_exact(self.request,1)
            if not headers.endswith(b'\r\n\r\n'): return
            fields = {}
            for line in headers.decode().split('\r\n')[1:]:
                if ':' in line:
                    k,v = line.split(':',1); fields[k.lower()] = v.strip()
            key=fields.get('sec-websocket-key','')
            accept=base64.b64encode(hashlib.sha1((key+_GUID).encode()).digest()).decode()
            if self.settings().get('bad_accept'): accept='AAAAAAAAAAAA'
            reply=('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n'
                'Connection: keep-alive, Upgrade\r\nSec-WebSocket-Accept: '+accept+'\r\n'
                + ('Sec-WebSocket-Extensions: permessage-deflate\r\n' if self.settings().get('bad_extension') else '')
                + '\r\n')
            self.request.sendall(reply.encode())
            if self.settings().get('handshake_only'): return
            while True:
                opcode,raw,fin,masked = receive(self.request)
                if opcode == 10: continue
                if opcode == 8: return
                if opcode != 1 or not fin or not masked: return
                doc=json.loads(raw)
                ident=doc.get('id'); method=doc.get('method')
                settings=self.settings()
                self.server.requests.append(doc)
                if method == 'initialize': self.reply(ident,{})
                elif method in ('thread/read','thread/resume'):
                    settings = {**settings, **settings.get('threads', {}).get(doc.get('params', {}).get('threadId'), {})}
                    if settings.get('missing'): self.respond({'id':ident,'error':{'code':-1,'message':'missing'}})
                    else:
                        self.reply(ident,{'thread':{'id':settings.get('returned_id',settings['thread']),
                            'cwd':settings.get('cwd',str(self.server.dev)),
                            'status':{'type':('systemError' if settings.get('partial_overload') and self.server.history
                                      else settings.get('thread_status','idle'))},
                            **({'turns':list(self.server.history.values())} if doc.get('params',{}).get('includeTurns') else {})}})
                elif method == 'thread/turns/list':
                    if settings.get('legacy_history'):
                        self.respond({'id':ident,'error':{'code':-32601,'message':'method not found'}})
                    else:
                        params = doc['params']; offset = int(params.get('cursor', '0'))
                        limit = params.get('limit', 50)
                        ordered = list(self.server.history.values())
                        if params.get('sortDirection', 'desc') == 'desc': ordered.reverse()
                        data = []
                        view = params.get('itemsView', 'summary')
                        for original in ordered[offset:offset+limit]:
                            value = {**original, 'itemsView': view}
                            if view == 'notLoaded': value['items'] = []
                            data.append(value)
                        following = str(offset + limit) if offset + limit < len(ordered) else None
                        self.reply(ident, {'data': data, 'nextCursor': following})
                elif method == 'thread/items/list':
                    if settings.get('no_item_pages'):
                        self.respond({'id':ident,'error':{'code':-32601,'message':'method not found'}})
                    else:
                        params = doc['params']; turn_id = params['turnId']
                        original = self.server.history.get(turn_id, {})
                        items = original.get('items', [])
                        if params.get('sortDirection', 'asc') == 'desc': items = list(reversed(items))
                        offset = int(params.get('cursor', '0')); limit = params.get('limit', 50)
                        data = [{'turnId':turn_id, 'item':item} for item in items[offset:offset+limit]]
                        following = str(offset + limit) if offset + limit < len(items) else None
                        self.reply(ident, {'data':data, 'nextCursor':following, 'backwardsCursor':None})
                elif method == 'thread/backgroundTerminals/list':
                    if settings.get('no_background_api'):
                        self.respond({'id':ident,'error':{'code':-32601,'message':'method not found'}})
                    else:
                        pending = [item for turn in self.server.history.values() for item in turn.get('items', [])
                                   if item.get('type') == 'commandExecution' and item.get('status') == 'inProgress'
                                   and item.get('processId')]
                        terminals = settings.get('background_terminals', [
                            {'processId': item['processId'], 'itemId': item['id'],
                             'command': item['command'], 'cwd': item['cwd'],
                             'cpuPercent': 15.0, 'rssKb': 4000, 'osPid': 1234} for item in pending])
                        params = doc['params']; offset = int(params.get('cursor', '0'))
                        limit = params.get('limit', 16)
                        following = str(offset+limit) if offset+limit < len(terminals) else None
                        self.reply(ident, {'data': terminals[offset:offset+limit], 'nextCursor': following})
                elif method == 'turn/start':
                    with (self.server.home / 'calls.jsonl').open('a') as out:
                        out.write(json.dumps(['app-server','unix'])+'\n')
                    params=doc['params']; turn='test-turn' if not self.server.history else 'test-turn-'+str(len(self.server.history)+1)
                    with (self.server.home/'request.json').open('w') as out: json.dump(params,out)
                    (self.server.home/'started').write_text('yes')
                    self.reply(ident,{'turn':{'id':turn,'status':'inProgress'}})
                    self.respond({'method':'turn/started','params':{'threadId':settings['thread'],'turn':{'id':turn,'status':'inProgress'}}})
                    prompt=params['input'][0]['text']
                    for event in settings.get('pre_events',[]):
                        self.respond(event)
                    if settings.get('slow'):
                        while not (self.server.home/'release').exists(): time.sleep(.02)
                    if settings.get('disconnect_turn'):
                        self.server.history[turn]={'id':turn,'status':'inProgress','items':[]}
                        return
                    if settings.get('overload'):
                        items=[{'id':'u','type':'userMessage','content':[{'type':'text','text':prompt}]},
                               {'id':'p','type':'commandExecution','command':'pwd','status':'completed','exitCode':0}]
                        if settings.get('partial_overload'):
                            (self.server.dev/'partial.txt').write_text('preserved local work')
                            items[0]['content'][0]['text_elements'] = []
                            items[1].update(cwd=str(self.server.dev), source='agent')
                            items.append({'id':'edit','type':'fileChange','status':'completed',
                                          'changes':[{'path':str(self.server.dev/'partial.txt')}]})
                        if settings.get('pending_overload'):
                            items.append({'id': 'catalog', 'type': 'commandExecution',
                                          'command': 'python3 -B tools/catalog.py', 'cwd': str(self.server.dev),
                                          'source': 'unifiedExecStartup', 'processId': 'owned-test-process',
                                          'commandActions': [], 'status': 'inProgress', 'exitCode': None,
                                          'durationMs': None, 'aggregatedOutput': ''})
                        failed={'id':turn,'status':'failed','items':items,'error':{'message':'Selected model is at capacity',
                                                                                        'codexErrorInfo':'serverOverloaded'}}
                        self.server.history[turn]=failed
                        self.respond({'method':'error','params':{'threadId':settings['thread'],'turnId':turn,
                                      'error':failed['error'],'willRetry':settings.get('will_retry',False)}})
                        self.respond({'method':'turn/completed','params':{'threadId':settings['thread'],'turn':failed}})
                        continue
                    if 'Sichtbarkeitstest' in prompt:
                        result={'marker':prompt.split('marker=')[-1]}
                    else:
                        source=json.loads(prompt.split('\n')[1])
                        if settings.get('mode','patch') == 'patch':
                            path = Path(settings['exchange'])/('dev-'+source['run_id']+'.zip')
                            facts={'kind':'patch','binding':source['binding']}
                            tmp=path.with_suffix('.partial')
                            with zipfile.ZipFile(tmp,'w') as z:
                                z.writestr('patch.json',json.dumps({**source['binding'],'marker':'patch-harbor', 'format_version':1,'entrypoint':'run.sh'}))
                                z.writestr('test-facts.json',json.dumps(facts))
                            tmp.replace(path)
                            result={'source_result_sha256':source['sha256'],'status':'patch_ready','patch_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'message':''}
                        else:
                            result={'source_result_sha256':source['sha256'],'status':settings['mode'],'patch_sha256':'','message':''}
                    self.server.history[turn]={'id':turn,'status':'failed' if settings.get('fail') else 'completed','items':[]}
                    self.respond({'method':'item/completed','params':{'threadId':settings['thread'],'turnId':turn,
                        'item':{'type':'agentMessage','text':json.dumps(result)}}})
                    self.respond({'method':'turn/completed','params':{'threadId':settings['thread'],
                        'turn':{'id':turn,'status':'failed' if settings.get('fail') else 'completed'}}})
                elif method and ident is not None: self.respond({'id':ident,'error':{'code':-1}})
        except (EOFError, OSError, ValueError, KeyError, json.JSONDecodeError):
            return


class SocketDaemon:
    def __init__(self, codex_home, dev):
        self.path=Path(codex_home)/'app-server-control'/'app-server-control.sock'
        self.path.parent.mkdir(mode=0o700,exist_ok=True)
        self.server=FakeServer(self.path,codex_home,dev)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)
        try: self.path.unlink()
        except FileNotFoundError: pass
