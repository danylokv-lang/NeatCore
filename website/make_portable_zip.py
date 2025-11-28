#!/usr/bin/env python3
"""Create portable ZIP for website downloads.
Usage:
  python website/make_portable_zip.py
Generates website/downloads/NeatCore.zip from dist/NeatCore build.
"""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / 'dist' / 'NeatCore'
OUT = ROOT / 'website' / 'downloads' / 'NeatCore.zip'

def main():
    if not DIST.exists():
        print('Build folder not found:', DIST)
        print('Run: pyinstaller NeatCore.spec')
        sys.exit(1)
    if OUT.exists():
        OUT.unlink()
    print('Zipping', DIST, '->', OUT)
    shutil.make_archive(str(OUT)[:-4], 'zip', DIST)
    print('Done.')

if __name__ == '__main__':
    main()
