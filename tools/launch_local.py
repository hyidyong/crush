#!/usr/bin/env python3
"""Run one private local backend and its same-origin browser client."""
from __future__ import annotations

import argparse
import getpass
import hashlib
import ipaddress
import os
from pathlib import Path
import re
import sys
import threading
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def profile_directory(profile: str, data_dir: str | Path | None = None, project: Path = ROOT) -> Path:
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', profile):
        raise ValueError('Profile must contain 1–48 letters, numbers, underscores, or hyphens')
    owner = str(os.getuid()) if hasattr(os, 'getuid') else hashlib.sha256(getpass.getuser().encode()).hexdigest()[:16]
    destination = Path(data_dir).expanduser().absolute() if data_dir else project / '.local/users' / owner / profile
    # Never silently write identities through a symlink into another directory.
    for component in (destination, *destination.parents):
        if component.is_symlink():
            raise ValueError('Use a private directory without symbolic links')
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination.chmod(0o700)
    if data_dir is None:
        for component in (destination.parent, destination.parent.parent, project / '.local'):
            component.chmod(0o700)
    return destination


def validate_bind(host: str, token: str | None) -> None:
    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = host.lower() == 'localhost'
    if not loopback and (not token or len(token) < 32):
        raise ValueError('Binding beyond localhost requires an explicit access token of at least 32 characters')


def create_web_app(*, profile='default', config=None, data_dir=None, host='127.0.0.1',
                   access_token=None, allowed_hosts=(), project=ROOT, build_client=True):
    from fastapi.staticfiles import StaticFiles
    from unsent.backend.app import create_app
    from unsent.backend.config import load_local_settings
    from tools.build_web import build
    project = Path(project)
    validate_bind(host, access_token)
    private = profile_directory(profile, data_dir, project)
    config_path = Path(config).expanduser() if config else (project / '.local/config.toml' if profile == 'default' else private / 'config.toml')
    try:
        settings = load_local_settings(config_path)
    except Exception:
        raise ValueError('Could not load the private model configuration; check its format locally') from None
    settings.data_dir = str(private)
    settings.catalog_path = str(project / 'assets/characters.json')
    settings.access_token = access_token
    extras = tuple(allowed_hosts) + (() if host in ('0.0.0.0', '::') else (host.lower(),))
    if any(not re.fullmatch(r'[A-Za-z0-9.-]+|::1', value) for value in extras):
        raise ValueError('Allowed hosts must be explicit hostnames or IP addresses without ports')
    settings.allowed_hosts = tuple(dict.fromkeys((*settings.allowed_hosts, *extras)))
    application = create_app(settings)
    output = build(project) if build_client else project / '.local/web'
    if output.is_dir():
        application.mount('/', StaticFiles(directory=output, html=True), name='browser-client')
    return application


def open_when_ready(url: str) -> None:
    def worker():
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=1) as response:
                    if response.status == 200:
                        webbrowser.open(url)
                        return
            except Exception:
                pass
            time.sleep(0.25)
    threading.Thread(target=worker, name='open-local-browser', daemon=True).start()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', default='default')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--access-token')
    parser.add_argument('--access-token-env', help='Read the connection token from this local environment variable')
    parser.add_argument('--allowed-host', action='append', default=[])
    parser.add_argument('--open', action='store_true', help='Open the local browser after the app starts')
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error('Port must be between 1 and 65535')
    if args.access_token and args.access_token_env:
        parser.error('Choose one access token source')
    token = os.environ.get(args.access_token_env) if args.access_token_env else args.access_token
    if args.access_token_env and not token:
        parser.error('The selected local access token environment variable is empty')
    try:
        application = create_web_app(profile=args.profile, config=args.config, data_dir=args.data_dir,
            host=args.host, access_token=token, allowed_hosts=args.allowed_host)
    except ValueError as error:
        parser.error(str(error))
    browser_host = '127.0.0.1' if args.host in ('0.0.0.0', '::') else args.host
    if ':' in browser_host:
        browser_host = '[' + browser_host + ']'
    url = f'http://{browser_host}:{args.port}/'
    print(f'Local app: {url}', flush=True)
    if args.open:
        open_when_ready(url)
    import uvicorn
    uvicorn.run(application, host=args.host, port=args.port, access_log=False)


if __name__ == '__main__':
    # Script execution otherwise puts only tools/ on sys.path.
    sys.path.insert(0, str(ROOT))
    main()
