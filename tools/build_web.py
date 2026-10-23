#!/usr/bin/env python3
"""Build the client-only browser bundle with a pinned, same-origin Python runtime.

The runtime cache and output live in ignored .local/. No backend modules, private
profiles, environment files, or local model configuration enter the browser ZIP.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_COMMIT = '5ab484fcee674a99492cceb7bf3340239da63d7a'
RUNTIME_BASE = f'https://raw.githubusercontent.com/pygame-web/archives/{RUNTIME_COMMIT}/'
RUNTIME_HASHES = {
    'pythons.js': 'e11be94dd16c29ccbb0387735df5888e0050766b2c58eae636911259e915765f',
    'cpythonrc.py': 'b97d4ddf862207d59907bdd1b62658a2eeca479bdbf80e733bc7a66d76efc9e4',
    'cpython312/main.js': 'b6663c0257a5b696f85bd5920a4ee7d1a579e80e62699ea31fbe0c872a0f64f9',
    'cpython312/main.wasm': '0d1fc2968ab55cad57076adea9876f00dba0749c1d93eb14cea6122945933c06',
    'cpython312/main.data': '3190c58638da69b7c90616428e9a655bdb45a5842483cc7adab2aa7696a26de2',
    'repo/index-090-cp312.json': 'f1a831ff5f21fc07bcaf064dab66f23051925bf8f4537bdeede6a30aa0606165',
    'repo/repodata.json': 'b4feabe133e96726ef92dd275ce2967d31da17985c44b5b1815de6b0ec4200a2',
    'repo/cp312/pygame_static-1.0-cp312-cp312-wasm32_bi_emscripten.whl': '8e6e6e122dec42e35e4cfc3cd033e6bc87719a7e25fad75ad2fe125aea6dd51e',
}
RUNTIME_FILES = tuple(RUNTIME_HASHES)

SAME_ORIGIN_ADAPTER = '''
# Same-origin repository adapter for this application's pinned runtime.
import aio.pep0723
_local_repo = str(platform.window.location.origin) + "/runtime/repo/"
aio.pep0723.Config.PKG_INDEXES = [_local_repo]
aio.pep0723.Config.dev_mode = 1
_original_async_repos = aio.pep0723.async_repos
async def _same_origin_repos():
    await _original_async_repos()
    for repo in aio.pep0723.Config.pkg_repolist:
        repo["-CDN-"] = _local_repo
aio.pep0723.async_repos = _same_origin_repos

'''


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def ensure_runtime(cache: Path) -> None:
    """Download immutable public runtime artifacts, verifying all cached bytes."""
    cache.mkdir(parents=True, exist_ok=True)

    def fetch(name: str) -> None:
        target = cache / name
        if target.is_symlink():
            raise ValueError('Runtime cache must not contain symlinks')
        if target.is_file() and digest(target) == RUNTIME_HASHES[name]:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        url = RUNTIME_BASE + ('' if name.startswith('repo/') else '0.9/') + name
        request = urllib.request.Request(url, headers={'User-Agent': 'Unsent-runtime-builder/0.2'})
        fd, partial_name = tempfile.mkstemp(prefix=target.name + '.', suffix='.partial', dir=target.parent)
        partial = Path(partial_name)
        try:
            with os.fdopen(fd, 'wb') as output, urllib.request.urlopen(request, timeout=60) as response:
                shutil.copyfileobj(response, output)
            if digest(partial) != RUNTIME_HASHES[name]:
                raise ValueError(f'Pinned runtime checksum mismatch: {name}')
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fetch, RUNTIME_FILES))


def package_client(project: Path, target: Path) -> Path:
    """Write an atomic ZIP using a narrow allowlist, never the repository root."""
    project = Path(project).resolve()
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    allowed = [project / 'src/unsent/__init__.py']
    for directory in ('client', 'domain', 'shared'):
        allowed.extend((project / 'src/unsent' / directory).rglob('*.py'))
    allowed.extend((project / 'assets').rglob('*'))
    fd, temporary_name = tempfile.mkstemp(prefix='client-', suffix='.zip', dir=target.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as package:
            for path in sorted(set(allowed)):
                relative = path.relative_to(project)
                if not path.is_file() or path.is_symlink():
                    continue
                if any(part.startswith('.') or part == '__pycache__' for part in relative.parts):
                    continue
                archive_path = path.relative_to(project / 'src') if relative.parts[0] == 'src' else relative
                package.write(path, archive_path.as_posix())
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def build(project: Path | None = None) -> Path:
    project = Path(project or ROOT).resolve()
    output = project / '.local/web'
    cache = project / '.local/web-runtime'
    ensure_runtime(cache)
    output.mkdir(parents=True, exist_ok=True)
    runtime = output / 'runtime'
    for name in RUNTIME_FILES:
        target = runtime / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cache / name, target)
    # Inject only into the output derivative; the pinned cache remains byte exact.
    startup = runtime / 'cpythonrc.py'
    original = startup.read_text(encoding='utf-8')
    anchor = 'async def import_site(__file__, run=True):'
    if original.count(anchor) != 1:
        raise ValueError('Pinned Python bootstrap injection anchor changed')
    startup.write_text(original.replace(anchor, SAME_ORIGIN_ADAPTER + anchor, 1), encoding='utf-8')
    package_client(project, output / 'app.zip')
    shutil.copyfile(project / 'web/template.tmpl', output / 'index.html')
    for name in ('bridge.js', 'bridge.css'):
        shutil.copyfile(project / 'web' / name, output / name)
    fonts = output / 'fonts'
    fonts.mkdir(exist_ok=True)
    for path in (project / 'assets/fonts').glob('*.ttf'):
        shutil.copyfile(path, fonts / path.name)
    (output / 'runtime-manifest.json').write_text(json.dumps({
        'source': RUNTIME_BASE, 'commit': RUNTIME_COMMIT,
        'sha256': RUNTIME_HASHES,
        'derivatives': {'cpythonrc.py': 'Same-origin repository adapter before import_site'},
    }, indent=2) + '\n', encoding='utf-8')
    return output


if __name__ == '__main__':
    print(build())
