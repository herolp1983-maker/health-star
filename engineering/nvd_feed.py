"""Fetch complete official NVD feeds before scanning; cache only verified public data."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import functools
import gzip
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import time
from urllib.request import Request, urlopen
import zlib

BASE = 'https://nvd.nist.gov/feeds/json/cve/2.0/'
ATTEMPTS = 12
READ_TIMEOUT = 30
MAX_SECONDS = 2400


def metadata(text):
    values = dict(line.split(':', 1) for line in text.splitlines() if ':' in line)
    digest = values.get('sha256', '').lower()
    if not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('NVD META SHA-256 missing or invalid')
    stamp = datetime.fromisoformat(values['lastModifiedDate'])
    if stamp.utcoffset() is None:
        raise ValueError('NVD META timestamp needs an offset')
    size, gzsize = int(values['size']), int(values['gzSize'])
    if not (0 < size <= 2_147_483_648 and 0 < gzsize <= 536_870_912):
        raise ValueError('NVD META size outside supported bounds')
    return {'sha256': digest, 'size': size, 'gzSize': gzsize,
            # cache.properties uses Dependency-Check's single-X formatter, not ISO offsets.
            'lastModifiedDate': stamp.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}


def remaining(deadline):
    seconds = deadline - time.monotonic()
    if seconds <= 0:
        raise TimeoutError('NVD preparation exceeded its 40-minute budget')
    return min(READ_TIMEOUT, seconds)


def verified(path, meta, deadline):
    if path.is_symlink():
        raise ValueError('NVD cache must contain ordinary files')
    if not path.is_file() or path.stat().st_size != meta['gzSize']:
        return False
    try:
        digest = hashlib.sha256(); size = 0
        with gzip.open(path, 'rb') as source:
            while block := source.read(1024 * 1024):
                remaining(deadline)
                size += len(block)
                if size > meta['size']:
                    return False
                digest.update(block)
        return size == meta['size'] and digest.hexdigest() == meta['sha256']
    except (OSError, EOFError, zlib.error):
        return False


def transfer(url, part, meta, deadline):
    if part.is_symlink():
        raise ValueError('NVD partial cache must contain ordinary files')
    offset = part.stat().st_size if part.exists() else 0
    if offset >= meta['gzSize']:
        part.unlink(); offset = 0
    headers = {'User-Agent': 'health-app-ci-nvd/1.0', 'Accept-Encoding': 'identity'}
    if offset:
        headers['Range'] = f'bytes={offset}-'
    with urlopen(Request(url, headers=headers), timeout=remaining(deadline)) as response:
        if response.status == 206:
            expected = f'bytes {offset}-{meta["gzSize"] - 1}/{meta["gzSize"]}'
            if response.headers.get('Content-Range') != expected:
                raise ValueError('NVD response has an inconsistent Content-Range')
        elif response.status == 200:
            # A server may ignore Range. Restart this file rather than append corrupt bytes.
            offset = 0
        else:
            raise ValueError('Unexpected NVD download status')
        length = response.headers.get('Content-Length')
        if length is not None and int(length) != meta['gzSize'] - offset:
            raise ValueError('NVD response length differs from current META')
        with part.open('ab' if offset else 'wb') as target:
            # read1 returns available bytes rather than waiting to fill a large
            # buffer; even a slow trickle must reach the global deadline check.
            while block := response.read1(64 * 1024):
                remaining(deadline)
                if target.tell() + len(block) > meta['gzSize']:
                    raise ValueError('NVD response exceeds declared feed size')
                target.write(block)
    if part.stat().st_size != meta['gzSize']:
        raise IOError('NVD download was truncated; retain partial bytes for bounded resume')


def fetch_feed(kind, cache, output, deadline):
    if not re.fullmatch(r'(?:20[0-9]{2}|modified)', str(kind)):
        raise ValueError('Invalid NVD feed identifier')
    name = f'nvdcve-2.0-{kind}'
    for attempt in range(ATTEMPTS):
        try:
            request = Request(BASE + name + '.meta', headers={'Accept-Encoding': 'identity'})
            with urlopen(request, timeout=remaining(deadline)) as response:
                chunks = []; length = 0
                while block := response.read1(1024):
                    remaining(deadline); length += len(block)
                    if length > 8192:
                        raise ValueError('NVD META exceeds supported size')
                    chunks.append(block)
                text = b''.join(chunks)
            if len(text) > 8192:
                raise ValueError('NVD META exceeds supported size')
            meta = metadata(text.decode('utf-8'))
            complete = cache / (name + '-' + meta['sha256'] + '.json.gz')
            part = complete.with_suffix('.part')
            if not verified(complete, meta, deadline):
                if not verified(part, meta, deadline):
                    transfer(BASE + name + '.json.gz', part, meta, deadline)
                if not verified(part, meta, deadline):
                    part.unlink(missing_ok=True)
                    raise ValueError('NVD feed failed uncompressed size/SHA-256 validation')
                os.replace(part, complete)
            # Publish neither META nor payload until this exact pair has been verified.
            temporary = output / (name + '.tmp')
            shutil.copyfile(complete, temporary)
            os.replace(temporary, output / (name + '.json.gz'))
            (output / (name + '.meta')).write_bytes(text)
            print(f'NVD {kind}: verified {meta["gzSize"]} compressed bytes', flush=True)
            return str(kind), meta
        except (OSError, ValueError, KeyError) as error:
            print(f'NVD {kind}: attempt {attempt + 1}/{ATTEMPTS} failed ({type(error).__name__})', flush=True)
            if attempt + 1 == ATTEMPTS:
                raise RuntimeError(f'NVD {kind}: all verified download attempts failed') from error
            delay = min(15, 2 ** (attempt + 1), remaining(deadline))
            time.sleep(delay)
    raise AssertionError('Unreachable')


def prepare(cache, output):
    cache.mkdir(parents=True, exist_ok=True)
    # The serving directory must be new and empty: no stale cache.properties or feed files.
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError('NVD serving directory must be empty')
    deadline = time.monotonic() + MAX_SECONDS
    year = datetime.now(timezone(timedelta(hours=14))).year
    kinds = [str(value) for value in range(2002, year + 1)] + ['modified']
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = dict(executor.map(lambda kind: fetch_feed(kind, cache, output, deadline), kinds))
    # Dependency-Check's native feed protocol; all complete yearly feeds remain included.
    properties = ['lastModifiedDate=' + results['modified']['lastModifiedDate']]
    properties.extend('lastModifiedDate.' + kind + '=' + results[kind]['lastModifiedDate'] for kind in kinds)
    (output / 'cache.properties').write_text('\n'.join(properties) + '\n', encoding='utf-8')
    print(f'NVD: complete verified feed set, {len(kinds)} feeds', flush=True)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def scan(output, project):
    handler = functools.partial(QuietHandler, directory=str(output.resolve()))
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
    try:
        with tempfile.TemporaryDirectory(prefix='hero-odc-') as database:
            env = {**os.environ,
                   'HERO_NVD_FEED_URL': f'http://127.0.0.1:{server.server_port}/nvdcve-2.0-{{0}}.json.gz',
                   'HERO_NVD_DATABASE': database}
            wrapper = [str(project.resolve() / 'gradlew.bat')] if os.name == 'nt' else ['bash', 'gradlew']
            command = wrapper + ['--no-daemon', '--console=plain', '--init-script',
                                 str(Path(__file__).resolve().with_name('dependency-check.init.gradle')),
                                 ':app:dependencyCheckAnalyze']
            subprocess.run(command, cwd=project, env=env, check=True)
    finally:
        server.shutdown(); server.server_close(); worker.join()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    prepare(args.cache, args.output)
    if not args.prepare_only:
        scan(args.output, Path(__file__).resolve().parents[1] / 'hero-health-android')


if __name__ == '__main__':
    main()
