# Library Expander

A Windows desktop app that downloads manga, manhwa, and manhua series and converts each chapter into a properly named PDF — ready to drop into your comic library.

Built with Python + tkinter. Uses [gallery-dl](https://github.com/mikf/gallery-dl) for downloading and [img2pdf](https://gitlab.mister-muffin.de/josch/img2pdf) for conversion.

![Python](https://img.shields.io/badge/python-3.11+-blue) ![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

---

## Features

- Paste a series URL and it downloads every chapter automatically
- Converts images to correctly numbered PDFs (`001.pdf`, `002 - Chapter Title.pdf`, etc.)
- Resume support — re-run a series to pick up newly released chapters without re-downloading old ones
- Download queue — stage multiple series and process them one by one
- Reads cookies directly from Chrome, Firefox, Edge, or Brave to handle sites that require login or bypass Cloudflare
- Cleans up raw image files after conversion
- Dark themed UI

---

## Getting started

### Option A — Standalone exe (recommended)

Run `build.bat`. It will download everything it needs and produce `dist\Library Expander.exe`. No Python required to run the exe.

### Option B — Run from source

1. Install Python 3.11+
2. Run `install.bat` (or `pip install gallery-dl img2pdf Pillow`)
3. Run `python app.py` or double-click `launch.vbs` to open without a console window

---

## Usage

1. Paste the series URL
2. Enter a folder name (this becomes the output folder and the name shown in your library)
3. Pick an output directory
4. Select the browser you use for the site (needed for sites behind Cloudflare or login)
5. Click **Add to Queue**, then **Start Queue**

PDFs are written flat into `{output dir}/{folder name}/`. Temporary image files are deleted automatically once conversion finishes.

### Resume mode

Check **Resume / add new chapters to existing folder** before adding a job. This skips chapters that already have a PDF and only converts new ones. Useful for ongoing series.

---

## Output structure

```
Comics/
  Solo Leveling/
    001.pdf
    002.pdf
    003 - The Awakening.pdf
    ...
```

---

## Supported sites

Anything supported by gallery-dl. See the full list at [github.com/mikf/gallery-dl](https://github.com/mikf/gallery-dl#supported-sites).

---

## Requirements

| Dependency | Purpose |
|---|---|
| [gallery-dl](https://github.com/mikf/gallery-dl) | Downloading images from manga sites |
| [img2pdf](https://gitlab.mister-muffin.de/josch/img2pdf) | Lossless image-to-PDF conversion |
| [Pillow](https://python-pillow.org/) | WebP to JPEG conversion (img2pdf doesn't support WebP natively) |
