"""Pure Mermaid/DOT source emitters over an already resolved DiagramData.

No TargetModel, graph traversal, project discovery or rendering tool is used.
Original graph membership and bindings arrive exclusively in the owned value.
"""
import json


def diagram_source_bytes(resolved, *, output_format, label_mode):
    """Encode resolved values using the admitted source and label profiles."""
    data = resolved.data
    nodes = {node['artifact_id']: node['diagram_id'] for node in data['nodes']}
    if output_format == 'mermaid':
        lines = ['%% GENERATED — DO NOT EDIT', '%% diagram_data_sha256: ' + resolved.sha256,
                 'flowchart LR']
        for node in data['nodes']:
            # Encode every title character, including existing entity markers.
            # The grammar sees only decimal entities inside a plain text label;
            # HTML, markdown, KaTeX and diagram directives never enter it.
            label = (node['artifact_id'] if label_mode == 'id' else
                     ''.join('#' + str(ord(c)) + ';' for c in _label_text(node['title'])))
            lines.append('  ' + node['diagram_id'] + '["' + label + '"]')
        for edge in data['edges']:
            lines.append('  ' + nodes[edge['source']] + ' ' + edge['diagram_id'] +
                         '@-->|"' + edge['type'] + '"| ' + nodes[edge['target']])
    else:
        lines = ['// GENERATED — DO NOT EDIT', '// diagram_data_sha256: ' + resolved.sha256,
                 'digraph specroad {']
        for node in data['nodes']:
            label = node['artifact_id'] if label_mode == 'id' else _label_text(node['title'])
            # JSON quoting protects DOT's quoted-string boundary and doubles
            # literal backslashes, including escString substitutions such as \N.
            lines.append('  ' + node['diagram_id'] + ' [label=' +
                         json.dumps(label, ensure_ascii=False) + '];')
        for edge in data['edges']:
            lines.append('  ' + nodes[edge['source']] + ' -> ' + nodes[edge['target']] +
                         ' [id=' + json.dumps(edge['diagram_id']) +
                         ', label=' + json.dumps(edge['type']) + '];')
        lines.append('}')
    return ('\n'.join(lines) + '\n').encode('utf-8')


def _label_text(title):
    # C0/C1 controls become visible literal escapes in source labels only.
    # The original title in DiagramData is neither normalized nor truncated.
    return ''.join('\\u' + format(ord(c), '04x')
                   if ord(c) < 32 or 127 <= ord(c) <= 159 else c for c in title)
