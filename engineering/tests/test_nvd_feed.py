"""Regression coverage for truncated NVD downloads and untrusted cache bytes."""
import gzip
import hashlib
import io
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import nvd_feed as n


class Response(io.BytesIO):
    def __init__(self, body, status=200, headers=None):
        super().__init__(body); self.status = status; self.headers = headers or {}


class FeedTests(unittest.TestCase):
    def setUp(self):
        self.plain = b'{"vulnerabilities":[]}'
        self.payload = gzip.compress(self.plain)
        self.meta = (f'lastModifiedDate:2026-10-21T00:00:00Z\nsize:{len(self.plain)}\n'
                     f'gzSize:{len(self.payload)}\nsha256:{hashlib.sha256(self.plain).hexdigest()}\n').encode()

    def run_download(self, responder, cache_seed=None):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); cache = root / 'cache'; output = root / 'output'
            cache.mkdir(); output.mkdir()
            if cache_seed:
                cache_seed(cache)
            def request(req, **kwargs):
                if req.full_url.endswith('.meta'):
                    return Response(self.meta)
                return responder(req)
            with patch.object(n, 'urlopen', side_effect=request), patch.object(n.time, 'sleep'):
                result = n.fetch_feed('2010', cache, output, time.monotonic() + 60)
            self.assertEqual((output / 'nvdcve-2.0-2010.json.gz').read_bytes(), self.payload)
            self.assertEqual(result[1]['sha256'], hashlib.sha256(self.plain).hexdigest())
            self.assertTrue((output / 'nvdcve-2.0-2010.meta').is_file())

    def test_truncated_response_resumes_at_retained_byte_and_verifies_hash(self):
        split = len(self.payload) // 2; calls = []
        def response(request):
            calls.append(request.get_header('Range'))
            if len(calls) == 1:
                return Response(self.payload[:split], headers={'Content-Length': str(len(self.payload))})
            self.assertEqual(request.get_header('Range'), f'bytes={split}-')
            return Response(self.payload[split:], 206, {'Content-Range': f'bytes {split}-{len(self.payload)-1}/{len(self.payload)}', 'Content-Length': str(len(self.payload)-split)})
        self.run_download(response)
        self.assertEqual(len(calls), 2)

    def test_ignored_range_restarts_file_instead_of_appending(self):
        calls = []
        def response(request):
            calls.append(request.get_header('Range'))
            return Response(self.payload[:10] if len(calls) == 1 else self.payload)
        self.run_download(response)
        self.assertEqual(calls, [None, 'bytes=10-'])

    def test_corrupt_restored_cache_is_replaced_not_trusted(self):
        calls = []
        def seed(cache):
            name = 'nvdcve-2.0-2010-' + hashlib.sha256(self.plain).hexdigest() + '.json.gz'
            (cache / name).write_bytes(self.payload[:-1] + bytes([self.payload[-1] ^ 1]))
        self.run_download(lambda req: (calls.append(req.full_url) or Response(self.payload)), seed)
        self.assertEqual(len(calls), 1)

    def test_fresh_meta_validates_cache_and_avoids_payload_network(self):
        def seed(cache):
            (cache / ('nvdcve-2.0-2010-' + hashlib.sha256(self.plain).hexdigest() + '.json.gz')).write_bytes(self.payload)
        self.run_download(lambda req: self.fail('Verified cached payload should be reused'), seed)

    def test_complete_partial_from_interrupted_publish_is_reused(self):
        def seed(cache):
            name = 'nvdcve-2.0-2010-' + hashlib.sha256(self.plain).hexdigest() + '.json.part'
            (cache / name).write_bytes(self.payload)
        self.run_download(lambda req: self.fail('Complete verified partial needs no retransmission'), seed)

    def test_slow_trickle_still_reaches_deadline_check(self):
        ticks = [0]
        class Trickle(Response):
            def read1(self, count):
                ticks[0] += 31
                return b'x'
        with tempfile.TemporaryDirectory() as folder, patch.object(n.time, 'monotonic', side_effect=lambda: ticks[0]), patch.object(n, 'urlopen', return_value=Trickle(b'')):
            with self.assertRaises(TimeoutError):
                n.transfer('https://example.invalid/feed', Path(folder) / 'part', {'gzSize':100}, 30)
            self.assertEqual(ticks[0], 31)

    def test_checksum_mismatch_is_bounded_and_never_published(self):
        self.meta = self.meta.replace(hashlib.sha256(self.plain).hexdigest().encode(), b'0' * 64)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); cache = root / 'cache'; output = root / 'output'; cache.mkdir(); output.mkdir()
            calls = []
            def request(req, **kwargs):
                if req.full_url.endswith('.meta'):
                    return Response(self.meta)
                calls.append(req.full_url); return Response(self.payload)
            with patch.object(n, 'urlopen', side_effect=request), patch.object(n.time, 'sleep'):
                with self.assertRaises(RuntimeError):
                    n.fetch_feed('2010', cache, output, time.monotonic() + 60)
            self.assertEqual(len(calls), n.ATTEMPTS)
            self.assertEqual(list(output.iterdir()), [])

    def test_invalid_meta_and_expired_budget_fail_closed(self):
        for malformed in ['sha256:bad', self.meta.decode().replace('gzSize:', 'missing:')]:
            with self.assertRaises((ValueError, KeyError)):
                n.metadata(malformed)
        with tempfile.TemporaryDirectory() as folder, patch.object(n, 'urlopen') as network:
            with self.assertRaises(TimeoutError):
                n.fetch_feed('2010', Path(folder), Path(folder), time.monotonic() - 1)
            network.assert_not_called()

    def test_complete_year_range_and_modified_feed_are_required_before_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); seen = []
            def fetch(kind, *args):
                seen.append(kind); return kind, n.metadata(self.meta.decode())
            with patch.object(n, 'fetch_feed', side_effect=fetch):
                n.prepare(root / 'cache', root / 'out')
            year = n.datetime.now(n.timezone(n.timedelta(hours=14))).year
            self.assertEqual(set(seen), {str(y) for y in range(2002, year + 1)} | {'modified'})
            self.assertIn('lastModifiedDate.modified=', (root / 'out/cache.properties').read_text())
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(n, 'fetch_feed', side_effect=RuntimeError('download failed')):
                with self.assertRaises(RuntimeError):
                    n.prepare(root / 'cache', root / 'out')
            self.assertFalse((root / 'out/cache.properties').exists())
