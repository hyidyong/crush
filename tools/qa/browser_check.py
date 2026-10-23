"""Launch the restored app's Playwright checks with evidence outside tracked source."""
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]


def main():
    environment=os.environ.copy()
    environment.setdefault('UNSENT_TEST_URL','http://127.0.0.1:8765')
    environment.setdefault('UNSENT_QA_DIR','/tmp/unsent-browser-qa')
    return subprocess.call([sys.executable,'-m','pytest','tests/browser','-m','browser','-q',*sys.argv[1:]],cwd=ROOT,env=environment)


if __name__=='__main__':raise SystemExit(main())
