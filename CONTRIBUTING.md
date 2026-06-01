# Contributing

## How to contribute

1. Fork the repo and create a branch from `main`
2. Make your changes
3. Test manually — run `python app.py` and verify the feature or fix works end to end
4. Open a pull request with a short description of what changed and why

## Running from source

```
pip install gallery-dl img2pdf Pillow
python app.py
```

Or double-click `launch.vbs` to run without a console window.

## Building the exe

```
build.bat
```

Output: `dist\Library Expander.exe`

## What's in scope

- Bug fixes
- Support for edge cases in chapter folder name parsing
- UI improvements
- Performance or reliability improvements to the download/convert pipeline

## What's out of scope

- Adding GUI frameworks other than tkinter
- Anything that requires bundling a separate binary alongside the exe
- Platform support beyond Windows (not planned)

## Code style

- No dead code
- Keep it simple — this is a single-file app and should stay that way
