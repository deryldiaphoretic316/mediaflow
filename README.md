# MediaFlow

Desktop app for organizing photos and videos on Windows: **copy**, **sort**, **deduplicate**, and edit basic **EXIF / file dates**.

Free and open source under the [MIT License](LICENSE).  
Author: **[Valerii Korobeinikov](https://github.com/vkgeorgia)**.  
Repository: [github.com/vkgeorgia/mediaflow](https://github.com/vkgeorgia/mediaflow).

## Features

- **Copy** — transfer media into `camera/year/month` or `year/month` folders
- **Sort** — reorganize existing libraries with rename / extension rules
- **Deduplicate** — match by name, size, date, or SHA-256 hash
- **Metadata** — edit EXIF fields and Windows file timestamps for a single file
- **Settings** — language (ru/en), theme, media-only filter, default paths

## Requirements

- Windows 10/11
- [Python](https://www.python.org/) 3.9+ on `PATH` (`py` or `python`)
- Optional but recommended: [ExifTool](https://exiftool.org/) on `PATH` (RAW / video camera & shoot date). Example: `winget install OliverBetz.ExifTool`
- For the desktop shell (optional): [Node.js](https://nodejs.org/) 18+, [Rust](https://rustup.rs/)

## Quick start (backend + browser)

```bat
run.bat
```

Then open [http://127.0.0.1:8765](http://127.0.0.1:8765).

`run.bat` creates `.venv` on first launch and installs dependencies from `requirements.txt`.

## Desktop shell (Tauri)

```bat
npm install
npm run dev
```

Production installers:

```bat
npm run build
```

Artifacts: `src-tauri\target\release\bundle\{msi,nsis}\`

## Configuration

- Runtime settings are stored in `settings.json` next to `app.py` (gitignored).
- See `settings.example.json` for the schema and defaults.

## Project layout

| Path | Role |
|------|------|
| `app.py` | FastAPI backend (REST + SSE) |
| `static/index.html` | Single-page UI (Alpine.js + Tailwind CDN) |
| `src-tauri/` | Tauri 2 desktop shell |
| `run.bat` | Windows dev launcher |
| `requirements.txt` | Python dependencies |

## Notes

- SMB destination is disabled in the MVP (same as the original macOS build).
- ExifTool is an **external** tool; it is not bundled. Without it, RAW/video may fall back to `mtime` and `camera=Unknown`.
- MPEG Program Stream files (`.mpg` / `.mpeg`): embedded EXIF cannot be written by ExifTool; file timestamps can still be edited.

## License

[MIT](LICENSE) © 2026 Valerii Korobeinikov

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
