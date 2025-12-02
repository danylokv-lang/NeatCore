# NeatCore – Intelligent File Cleaner

NeatCore is a Windows desktop application that intelligently scans your folders, classifies files, detects duplicates (exact + perceptual) and provides clear, safe recommendations (delete / move / compress). It focuses on speed, transparency and low resource usage with optional AI (CLIP) for richer image classification.

## Core Features
- Streaming multi-folder scan (responsive even on large trees)
- Classification: images, screenshots, documents, media, archives, misc
- Duplicate detection: exact (MD5) + perceptual image similarity (pHash)
- Rule-based recommendations (age, location, quality, duplication)
- Safe deletions: Recycle Bin via `send2trash`
- Bulk move (archive) and ZIP compression
- Optional CLIP integration (lazy-loaded) for image semantics
- Fast Mode: skips heavy/system/build folders for triage
- Transparent reasons: every recommendation lists its rationale

## Install (Windows, Python 3.10+ recommended)
```powershell
# From project root
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Optional: CPU-only PyTorch (required for CLIP)
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

If `transformers` or `torch` is not installed, the app gracefully falls back to heuristics.

## Run (Development)
```powershell
.\.venv\Scripts\Activate.ps1
python main.py
```

## How It Works
- Scanner: walks directories, collects metadata, optional MD5
- Analyzer: classifies files (heuristics + optional CLIP), estimates image quality
- Duplicates: groups exact and perceptual duplicates (pHash)
- Recommender: suggests actions based on simple rules:
  - Old screenshots (> 30 days) → delete
  - Downloads folder files (> 90 days) → delete/move
  - Low-quality photos → delete
  - Duplicates → delete duplicates (keep best)

## Notes & Design Decisions
- Perceptual hashing uses `imagehash.phash` (Pillow backend)
- Delete uses Recycle Bin via `send2trash`
- Compress packs selected files to a ZIP

## Troubleshooting
- Large folders: first pass may take time, enable/disable duplicate and AI toggles for speed
- CLIP model download: the first AI classification triggers Hugging Face model download (cached afterwards)

## Project Structure
## Website
A static landing page lives in `website/` providing:
- Product overview and feature cards
- Download buttons (portable ZIP + installer EXE)
- FAQ and How It Works sections
- Theme toggle (dark/light)

Generate the portable build and place artifacts:
```powershell
pyinstaller NeatCore.spec
python website\make_portable_zip.py
copy installer\dist-installer\NeatCore-Setup.exe website\downloads\NeatCore-Setup.exe
```
Serve locally:
```powershell
cd website
python -m http.server 8000
```
Then visit http://localhost:8000

## Building Installer
Use Inno Setup script `installer/ai-file-cleaner.iss` (retained name for history) to package the ONEDIR build. It now includes the whole PyInstaller folder so embedded Python DLLs are present.

## Icon Pipeline
- Source icon: `assets/icon.png`
- Convert to ICO for PyInstaller: `python build_icon.py`
- Spec file references `assets/icon.ico`

## Roadmap / Ideas
- Integrate screenshot OCR (optional) for semantic duplicate detection
- Add disk usage charts and interactive pruning summaries
- Cross-platform (macOS/Linux) packaging
- Automatic update checker

## License
Pending (choose MIT / Apache-2.0 before public release). Currently unpublished license—do not redistribute binaries externally.

## Security Considerations
- No automatic destructive actions; user must confirm all file operations.
- All deletes reversible (Recycle Bin) unless user manually empties it.

## Contributing
1. Fork / clone repository
2. Create virtual environment & install dependencies
3. Submit PR with focused changes (avoid unrelated refactors)

## Acknowledgements
- PySide6, qt-material for UI theming
- Pillow + imagehash for perceptual hashing
- send2trash for safe deletion
- Optional: Hugging Face Transformers / CLIP model

---
NeatCore keeps your storage healthy by highlighting what matters—and why.
```
core/
  scanner.py       # scans files and metadata
  analyze.py       # classification + quality heuristics (CLIP optional)
  duplicates.py    # exact + perceptual duplicates
  recommend.py     # rule-based suggestions
  utils.py         # helpers
ui/
  main_window.py   # main UI
  workers.py       # background threads
main.py            # app entrypoint
requirements.txt
README.md
```
# NeatCore
