from __future__ import annotations
import json, urllib.error, urllib.request
from typing import Any, Callable

class APIError(RuntimeError): pass
class CancelledError(APIError): pass

def _request(endpoint, api_key, payload, accept='application/json'):
    return urllib.request.Request(endpoint,data=json.dumps(payload).encode(),method='POST',headers={'Authorization':f'Bearer {api_key}','Content-Type':'application/json','Accept':accept,'User-Agent':'Codex-Termux-Agent/2.0'})

def post_json(endpoint: str, api_key: str, payload: dict[str, Any], timeout: int = 120) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(_request(endpoint,api_key,payload),timeout=timeout) as response:
            raw=response.read().decode('utf-8','replace'); obj=json.loads(raw); obj['_codex_meta']={'usage':obj.get('usage') or {}, 'rate_limits':{k:v for k,v in response.headers.items() if 'ratelimit' in k.lower() or 'retry-after' in k.lower()}}; return obj
    except urllib.error.HTTPError as exc:
        body=exc.read().decode('utf-8','replace')
        try:
            parsed=json.loads(body); message=parsed.get('error',{}).get('message') or parsed.get('message') or body
        except json.JSONDecodeError: message=body or str(exc.reason)
        raise APIError(f'HTTP {exc.code}: {message}') from exc
    except urllib.error.URLError as exc: raise APIError(f'Koneksi gagal: {exc.reason}') from exc
    except TimeoutError as exc: raise APIError('Request timeout.') from exc

def stream_json(endpoint: str, api_key: str, payload: dict[str, Any], timeout: int = 120, on_token: Callable[[str],None] | None = None, cancel_event=None, on_response: Callable[[Any], None] | None = None) -> dict[str, Any]:
    """Consume OpenAI-compatible SSE and reconstruct a normal chat response."""
    data=dict(payload); data['stream']=True
    content=[]; tool_map={}; finish=None; usage=None; rate_limits={}
    try:
        with urllib.request.urlopen(_request(endpoint,api_key,data,'text/event-stream'),timeout=timeout) as response:
            if on_response: on_response(response)
            if cancel_event is not None and cancel_event.is_set():
                raise CancelledError('Operasi dibatalkan oleh pengguna.')
            rate_limits={k:v for k,v in response.headers.items() if 'ratelimit' in k.lower() or 'retry-after' in k.lower()}
            buffer=''
            while True:
                # read1/readline avoids urllib buffering a large chunk before emitting SSE tokens.
                if cancel_event is not None and cancel_event.is_set():
                    raise CancelledError('Operasi dibatalkan oleh pengguna.')
                chunk=response.read1(4096) if hasattr(response, 'read1') else response.readline()
                if not chunk: break
                buffer += chunk.decode('utf-8','replace')
                lines=buffer.split('\n'); buffer=lines.pop()
                for line in lines:
                    line=line.strip()
                    if not line.startswith('data:'): continue
                    raw=line[5:].strip()
                    if raw=='[DONE]': continue
                    try: obj=json.loads(raw)
                    except json.JSONDecodeError: continue
                    if obj.get('usage'): usage=obj['usage']
                    choices=obj.get('choices') or []
                    if not choices: continue
                    delta=choices[0].get('delta') or {}
                    piece=delta.get('content')
                    if not isinstance(piece, str) and isinstance(delta.get('refusal'), str):
                        piece = delta.get('refusal')
                    if isinstance(piece,str):
                        content.append(piece)
                        if on_token: on_token(piece)
                    for tc in delta.get('tool_calls') or []:
                        idx=tc.get('index',0); entry=tool_map.setdefault(idx,{'id':tc.get('id',''),'type':'function','function':{'name':'','arguments':''}})
                        if tc.get('id'): entry['id']=tc['id']
                        fn=tc.get('function') or {}
                        entry['function']['name'] += fn.get('name') or ''
                        entry['function']['arguments'] += fn.get('arguments') or ''
                    if choices[0].get('finish_reason'): finish=choices[0]['finish_reason']
    except urllib.error.HTTPError as exc:
        body=exc.read().decode('utf-8','replace'); raise APIError(f'HTTP {exc.code}: {body}') from exc
    except urllib.error.URLError as exc: raise APIError(f'Koneksi gagal: {exc.reason}') from exc
    except TimeoutError as exc: raise APIError('Request timeout.') from exc
    return {'choices':[{'message':{'role':'assistant','content':''.join(content),'tool_calls':[tool_map[k] for k in sorted(tool_map)]},'finish_reason':finish}], 'usage':usage, '_codex_meta':{'usage':usage or {}, 'rate_limits':rate_limits}}

def extract_text(response: dict[str, Any]) -> str:
    choices=response.get('choices') or []
    if not choices: return '[Respons API tidak memiliki choices.]'
    message=choices[0].get('message') or {}; content=message.get('content')
    if isinstance(content,str): return content
    if isinstance(content,list):
        return ''.join(item.get('text','') for item in content if isinstance(item,dict))
    refusal = message.get('refusal')
    if isinstance(refusal, str) and refusal:
        return refusal
    if isinstance(response.get('refusal'), str):
        return response['refusal']
    return str(content or '')
