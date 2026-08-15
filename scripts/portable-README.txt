# MediaFlow — portable (Windows)

## Run

1. Double-click `MediaFlow.exe`.
2. Keep this whole folder together — do not move the exe alone.

Settings are saved as `settings.json` in this folder (created on first use).

## Requirements

- Windows 10/11 (64-bit)
- [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/) (usually already installed)

## Optional: ExifTool

For accurate camera / shoot-date metadata on RAW and video files, install
[ExifTool](https://exiftool.org/) and put `exiftool.exe` on your system `PATH`
(example: `winget install OliverBetz.ExifTool`), then restart MediaFlow.

Without ExifTool, JPEG/HEIC still work via Pillow; RAW/video may fall back to
file modification time and `camera=Unknown`.

## Notes

- The `runtime\` folder is a private Python environment. Do not delete it.
- `static\` and `app.py` are required by the app — leave them in place.
- SMB network destinations are disabled in this build.
- Free software under the MIT License. Author: Valerii Korobeinikov.
