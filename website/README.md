# NeatCore Website

A lightweight static landing page for NeatCore – the intelligent file cleaner.

## Structure
```
website/
  index.html            # Landing page
  assets/
    style.css           # Styles
    script.js           # Interactions
  downloads/            # Place built artifacts here
    NeatCore.zip        # Portable build (add manually)
    NeatCore-Setup.exe  # Installer (optional)
```

## Preparing a Download
1. Build icon (if not done):
   ```powershell
   python build_icon.py
   ```
2. Build the application (ONEDIR preferred for portable ZIP):
   ```powershell
   pyinstaller NeatCore.spec
   ```
3. Create a ZIP of the build folder:
   ```powershell
   powershell -Command "Compress-Archive -Path dist/NeatCore/* -DestinationPath website/downloads/NeatCore.zip -Force"
   ```
4. (Optional) Build installer via Inno Setup – copy resulting `NeatCore-Setup.exe` into `website/downloads/`.

## Hash (Optional)
Generate a SHA256 checksum for integrity and update the hash text in `index.html`:
```powershell
Get-FileHash website/downloads/NeatCore.zip -Algorithm SHA256 | Select-Object -ExpandProperty Hash
```

## Hosting Options
- **GitHub Pages**: Create a separate repo or `gh-pages` branch; place contents of `website/` at root. GitHub Pages will serve `index.html`.
- **Static Host (Netlify / Vercel)**: Drag and drop `website/` folder; ensure downloads directory is included.
- **Self-Hosting (Nginx)**: Point document root to `website/` folder; set correct MIME types.

## Updating Version
Change the version line in `index.html` (`Current Version:` span) and rebuild downloads.

## Customization
- Replace `../assets/icon.png` reference with hosted CDN if desired.
- Add screenshots: Place them in `website/assets/` and reference inside new `<section>`.

## License / Attribution
Ensure any third‑party libraries (if added later) are properly credited. Current site is custom and license‑free.

## Security Note
Do not host unsigned executables from untrusted sources. Consider code signing for production distribution.
