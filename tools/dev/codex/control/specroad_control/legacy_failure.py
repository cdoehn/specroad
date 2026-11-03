"""Read existing private v0.2 job evidence; never manufacture a completion."""
import os
import stat
from .codex_proxy import MAX_LOG, MAX_LINE
from .errors import ControlError
from .local import decode_object, outside
from .turn_errors import failure_details, error_code


def from_events(path, thread_id, turn_id):
    outside(path)
    try:
        fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    except OSError:
        raise ControlError('retry_evidence_missing','Legacy Codex event evidence is unavailable.') from None
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or before.st_mode & 0o077
                or before.st_nlink != 1 or not 0 < before.st_size < MAX_LOG):
            raise ControlError('retry_evidence_invalid','Legacy event evidence must be private and complete.')
        started = completed = 0
        notification = terminal = None
        with os.fdopen(fd,'rb',closefd=False) as stream:
            total=0
            while True:
                raw=stream.readline(MAX_LINE+1)
                if not raw:break
                total+=len(raw)
                if total>=MAX_LOG or len(raw)>MAX_LINE or not raw.endswith(b'\n'):
                    raise ValueError
                event=decode_object(raw)
                data=event.get('params',{})
                if not isinstance(data,dict) or data.get('threadId') != thread_id:continue
                method=event.get('method')
                if method=='turn/started' and data.get('turn',{}).get('id')==turn_id:
                    started+=1
                if method=='error' and data.get('turnId')==turn_id:
                    notification=data
                if method=='turn/completed' and data.get('turn',{}).get('id')==turn_id:
                    completed+=1;terminal=data['turn']
        after=os.fstat(fd)
        if (before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):
            raise ValueError
        if started != 1 or completed != 1 or not terminal or not notification:
            raise ValueError
        if terminal.get('status') != 'failed' or error_code(terminal.get('error')) != 'serverOverloaded' or error_code(notification.get('error')) != 'serverOverloaded':
            raise ValueError
        return {'thread_id':thread_id,'turn_id':turn_id,**failure_details(terminal,notification)}
    except (ValueError,TypeError,KeyError,UnicodeError,RecursionError,OSError,AttributeError):
        raise ControlError('retry_evidence_invalid','Legacy log lacks unambiguous matching terminal failure evidence.') from None
    finally:
        os.close(fd)
