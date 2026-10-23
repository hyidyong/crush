#!/usr/bin/env python3
"""Audit committed/staged source without displaying matched credential values."""
import argparse,re,subprocess,sys
from pathlib import Path

PATTERNS={
    'provider-key':rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}',
    'github-token':rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})',
    'private-key':rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'aws-access-key':rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'url-credentials':rb'https?://[^\s/"\'<>]+:[^\s/"\'<>]+@',
}

def audit(staged=False):
    root=Path(__file__).resolve().parents[1];failures=[]
    paths=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode().split('\0')
    for name in filter(None,paths):
        parts=Path(name).parts
        if any(part in ('.local','.venv','__pycache__') or part.startswith('.env') for part in parts):failures.append((name,'private-path'));continue
        if staged:
            result=subprocess.run(['git','show',':'+name],cwd=root,capture_output=True)
            if result.returncode:continue
            data=result.stdout
        else:data=(root/name).read_bytes()
        if b'\0' in data[:4096]:continue
        for label,pattern in PATTERNS.items():
            if re.search(pattern,data):failures.append((name,label))
    if failures:
        for name,label in failures:print(f'{name}: {label} matched; value withheld')
        return 1
    print(f'Public source audit passed ({sum(bool(path) for path in paths)} files; no credential values printed).');return 0

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--staged',action='store_true');sys.exit(audit(parser.parse_args().staged))
