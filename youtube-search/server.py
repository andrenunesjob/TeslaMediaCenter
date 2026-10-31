"""Small WSGI search service. Playback stays in YouTube's official embed."""
import json
import os
import re
import subprocess
import sys
import threading
import time
from collections import OrderedDict, deque
from urllib.parse import parse_qs

ALLOWED_ORIGINS = frozenset(filter(None, (value.strip() for value in os.getenv(
    'ALLOWED_ORIGINS', 'https://andrenunesjob.github.io').split(','))))
CACHE_TTL = 300
CACHE_SIZE = 128
REQUESTS_PER_MINUTE = 60
_lock = threading.Lock()
_search_slot = threading.BoundedSemaphore(1)
_cache = OrderedDict()
_requests = deque()


def extract(query):
    result = subprocess.run([
        sys.executable, '-m', 'yt_dlp', '--ignore-config', '--no-cache-dir',
        '--no-warnings', '--skip-download', '--flat-playlist', '--dump-single-json',
        '--socket-timeout', '8', '--retries', '1', '--extractor-retries', '1',
        '--', 'ytsearch12:' + query,
    ], capture_output=True, text=True, timeout=20, check=True)
    data = json.loads(result.stdout)
    if not isinstance(data, dict) or not isinstance(data.get('entries'), list):
        raise ValueError('Invalid extractor response')
    items = []
    for entry in data.get('entries', []):
        if not isinstance(entry, dict) or not re.fullmatch(r'[A-Za-z0-9_-]{11}', str(entry.get('id', ''))):
            continue
        video_id = entry['id']
        items.append({
            'id': video_id,
            'title': str(entry.get('title') or 'Sem título'),
            'channel': str(entry.get('channel') or entry.get('uploader') or ''),
            'thumb': f'https://i.ytimg.com/vi/{video_id}/mqdefault.jpg',
        })
    return items[:12]


def application(environ, start_response):
    origin = environ.get('HTTP_ORIGIN', '')
    headers = [('Content-Type', 'application/json; charset=utf-8'),
               ('Cache-Control', 'no-store'), ('Vary', 'Origin'),
               ('X-Content-Type-Options', 'nosniff')]
    if origin in ALLOWED_ORIGINS:
        headers.append(('Access-Control-Allow-Origin', origin))

    def respond(status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        start_response(status, headers + [('Content-Length', str(len(body)))])
        return [body]

    if origin and origin not in ALLOWED_ORIGINS:
        return respond('403 Forbidden', {'error': 'Esta origem não está autorizada no serviço de pesquisa.'})
    if environ.get('REQUEST_METHOD') != 'GET':
        headers.append(('Allow', 'GET'))
        return respond('405 Method Not Allowed', {'error': 'Usa GET.'})
    path = environ.get('PATH_INFO', '')
    if path == '/health':
        return respond('200 OK', {'status': 'ok'})
    if path != '/api/search':
        return respond('404 Not Found', {'error': 'Endpoint não encontrado.'})
    query_string = environ.get('QUERY_STRING', '')
    if len(query_string) > 2000:
        return respond('400 Bad Request', {'error': 'Pesquisa demasiado longa.'})
    try:
        values = parse_qs(query_string, max_num_fields=4)
    except ValueError:
        return respond('400 Bad Request', {'error': 'Parâmetros inválidos.'})
    if set(values) != {'q'} or len(values['q']) != 1:
        return respond('400 Bad Request', {'error': 'Usa apenas o parâmetro q.'})
    query = values['q'][0].strip()
    if not 2 <= len(query) <= 200 or any(ord(c) < 32 or ord(c) == 127 for c in query):
        return respond('400 Bad Request', {'error': 'A pesquisa deve ter entre 2 e 200 caracteres, sem caracteres de controlo.'})
    now = time.monotonic()
    with _lock:
        while _requests and _requests[0] <= now - 60:
            _requests.popleft()
        if len(_requests) >= REQUESTS_PER_MINUTE:
            headers.append(('Retry-After', '60'))
            return respond('429 Too Many Requests', {'error': 'Limite de pesquisas atingido. Tenta dentro de um minuto.'})
        _requests.append(now)
        cached = _cache.get(query)
        if cached and now - cached[0] < CACHE_TTL:
            _cache.move_to_end(query)
            return respond('200 OK', {'items': cached[1]})
        _cache.pop(query, None)
    if not _search_slot.acquire(blocking=False):
        headers.append(('Retry-After', '5'))
        return respond('429 Too Many Requests', {'error': 'Outra pesquisa está em curso. Tenta novamente em poucos segundos.'})
    try:
        items = extract(query)
    except subprocess.TimeoutExpired:
        return respond('504 Gateway Timeout', {'error': 'O YouTube demorou demasiado a responder. Tenta novamente.'})
    except (subprocess.CalledProcessError, ValueError, OSError):
        # Extractor output can contain sensitive provider/network details; do not expose it.
        return respond('502 Bad Gateway', {'error': 'A pesquisa YouTube falhou. Pode existir um bloqueio do IP da VPS ou uma alteração no YouTube. Atualiza o serviço e tenta novamente.'})
    finally:
        _search_slot.release()
    with _lock:
        _cache[query] = (time.monotonic(), items)
        _cache.move_to_end(query)
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return respond('200 OK', {'items': items})


if __name__ == '__main__':
    from waitress import serve
    serve(application, host='0.0.0.0', port=8080, threads=4, connection_limit=64,
          channel_timeout=40, max_request_body_size=1024, ident='YouTubeSearch')
