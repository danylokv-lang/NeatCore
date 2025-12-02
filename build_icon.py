#!/usr/bin/env python3
"""Generate multi-size ICO from assets/icon.png.
Run:
  python build_icon.py
Creates assets/icon.ico for PyInstaller & installer usage.
"""
from pathlib import Path
from PIL import Image

def main():
    root = Path(__file__).parent
    png = root / 'assets' / 'icon.png'
    ico = root / 'assets' / 'icon.ico'
    if not png.exists():
        print('PNG not found:', png)
        return
    img = Image.open(png).convert('RGBA')
    sizes = [(256,256),(128,128),(64,64),(48,48),(32,32),(24,24),(16,16)]
    img.save(ico, sizes=sizes)
    print('Wrote', ico)

if __name__ == '__main__':
    main()
