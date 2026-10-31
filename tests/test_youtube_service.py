"""Service contract and extractor isolation tests; no real YouTube traffic."""
import importlib.util
import json
from pathlib import Path
import subprocess
import threading
import unittest
from unittest.mock import patch, Mock
from urllib.parse import urlencode

spec = importlib.util.spec_from_file_location('youtube_service', Path(__file__).resolve().parents[1] / 'youtube-search/server.py')
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


class YouTubeService(unittest.TestCase):
    def setUp(self):
        service._cache.clear()
        service._requests.clear()
        service._search_slot = threading.BoundedSemaphore(1)

    def request(self, query='music', origin='https://andrenunesjob.github.io', path='/api/search', method='GET', raw=None):
        captured = {}
        def start(status, headers):
            captured.update(status=status, headers=dict(headers))
        body = b''.join(service.application({
            'REQUEST_METHOD': method, 'PATH_INFO': path,
            'QUERY_STRING': raw if raw is not None else urlencode({'q': query}), 'HTTP_ORIGIN': origin,
        }, start))
        return captured['status'], captured['headers'], json.loads(body)

    def test_search_cache_and_cors(self):
        items = [{'id': 'dQw4w9WgXcQ', 'title': 'Demo', 'channel': 'Demo'}]
        with patch.object(service, 'extract', return_value=items) as extract:
            status, headers, body = self.request()
            self.assertEqual(status, '200 OK')
            self.assertEqual(body['items'], items)
            self.assertEqual(headers['Access-Control-Allow-Origin'], 'https://andrenunesjob.github.io')
            self.request()
            extract.assert_called_once_with('music')

    def test_invalid_requests_never_invoke_extractor(self):
        with patch.object(service, 'extract') as extract:
            for query in ['', 'a', 'x' * 201, 'ab\ncd']:
                self.assertTrue(self.request(query=query)[0].startswith('400'))
            for raw in ['url=https://example.com', 'q=one&q=two', 'q=test&url=x']:
                self.assertTrue(self.request(raw=raw)[0].startswith('400'))
            status, headers, _ = self.request(origin='https://unrelated.example')
            self.assertEqual(status, '403 Forbidden')
            self.assertNotIn('Access-Control-Allow-Origin', headers)
            self.assertTrue(self.request(method='POST')[0].startswith('405'))
            self.assertTrue(self.request(path='/unknown')[0].startswith('404'))
            extract.assert_not_called()

    def test_upstream_failure_and_timeout_release_search_slot(self):
        for error, status in [(subprocess.TimeoutExpired('yt-dlp', 20), '504'), (subprocess.CalledProcessError(1, 'yt-dlp', stderr='private diagnostics'), '502')]:
            with patch.object(service, 'extract', side_effect=error):
                result, _, body = self.request()
                self.assertTrue(result.startswith(status))
                self.assertNotIn('private diagnostics', json.dumps(body))
            with patch.object(service, 'extract', return_value=[]):
                self.assertEqual(self.request()[0], '200 OK')
            service._cache.clear()

    def test_busy_and_rate_limits(self):
        service._search_slot.acquire()
        with patch.object(service, 'extract') as extract:
            self.assertTrue(self.request()[0].startswith('429'))
            service._search_slot.release()
            with patch.object(service, 'REQUESTS_PER_MINUTE', 1):
                self.assertTrue(self.request()[0].startswith('429'))
            extract.assert_not_called()

    def test_extractor_uses_fixed_search_prefix_without_shell(self):
        output = {'entries': [None, {'id': 'invalid'}, {'id': 'dQw4w9WgXcQ', 'title': '<b>Demo</b>', 'uploader': 'Demo'}]}
        with patch.object(service.subprocess, 'run', return_value=Mock(stdout=json.dumps(output))) as run:
            items = service.extract('test; echo injected')
            args, kwargs = run.call_args
            self.assertEqual(args[0][-1], 'ytsearch12:test; echo injected')
            self.assertNotIn('shell', kwargs)
            self.assertEqual(kwargs['timeout'], 20)
            self.assertEqual(items, [{'id': 'dQw4w9WgXcQ', 'title': '<b>Demo</b>', 'channel': 'Demo', 'thumb': 'https://i.ytimg.com/vi/dQw4w9WgXcQ/mqdefault.jpg'}])

    def test_health_is_not_an_upstream_readiness_claim(self):
        with patch.object(service, 'extract') as extract:
            self.assertEqual(self.request(path='/health', origin='')[2], {'status': 'ok'})
            extract.assert_not_called()
