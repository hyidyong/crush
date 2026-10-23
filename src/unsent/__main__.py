"""Native Pygame entry point; private state stays in the selected local profile."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import getpass
import os
from pathlib import Path
import re


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path)
    parser.add_argument('--backend', default='http://127.0.0.1:8765')
    parser.add_argument('--no-backend', action='store_true')
    parser.add_argument('--access-token')
    parser.add_argument('--access-token-env')
    parser.add_argument('--profile', default='default')
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--width', type=int, default=414)
    parser.add_argument('--height', type=int, default=896)
    parser.add_argument('--frames', type=int, default=0)
    parser.add_argument('--screenshot', type=Path)
    parser.add_argument('--screen', default='inbox')
    args = parser.parse_args(argv)
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', args.profile):
        parser.error('Use 1–48 letters, numbers, underscores, or hyphens for the profile')
    if min(args.width, args.height) < 200 or args.frames < 0:
        parser.error('Window dimensions must be at least 200; frames cannot be negative')
    if args.access_token and args.access_token_env:
        parser.error('Choose one access token source')
    root = Path(__file__).resolve().parents[2]
    owner = str(os.getuid()) if hasattr(os, 'getuid') else hashlib.sha256(getpass.getuser().encode()).hexdigest()[:16]
    private = args.data_dir.expanduser().absolute() if args.data_dir else root / '.local/users' / owner / args.profile
    if any(part.is_symlink() for part in (private, *private.parents)):
        parser.error('Use a private directory without symbolic links')
    private.mkdir(parents=True, exist_ok=True, mode=0o700)
    private.chmod(0o700)
    token = os.getenv(args.access_token_env) if args.access_token_env else args.access_token
    if args.access_token_env and not token:
        parser.error('The selected local access token environment variable is empty')
    from unsent.client.app import ClientConfig, run
    config = ClientConfig(asset_root=args.assets or root / 'assets', backend_url=None if args.no_backend else args.backend,
        token=token, width=args.width, height=args.height, frames=args.frames, screenshot=args.screenshot,
        initial_screen=args.screen, data_dir=private)
    asyncio.run(run(config))


if __name__ == '__main__':
    main()
