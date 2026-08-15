# MediaFlow

## Download (Windows portable)

Скачайте именно этот файл: **`MediaFlow-portable-0.1.0-win64.zip`**

- из репозитория: [releases/MediaFlow-portable-0.1.0-win64.zip](https://github.com/vkgeorgia/mediaflow/raw/master/releases/MediaFlow-portable-0.1.0-win64.zip)
- или со страницы [Releases](https://github.com/vkgeorgia/mediaflow/releases) (тот же архив)

Распакуйте и запустите `MediaFlow.exe`. Системный Python не нужен. Не вытаскивайте exe отдельно — рядом должны остаться `runtime\`, `app.py` и `static\`.

---

Desktop app for organizing photos and videos: **copy**, **sort**, **deduplicate**, and edit basic **EXIF / file dates**.

Free and open source under the [MIT License](LICENSE).  
Author: **[Valerii Korobeinikov](https://github.com/vkgeorgia)**.  
Repository: [github.com/vkgeorgia/mediaflow](https://github.com/vkgeorgia/mediaflow).

Primary development and packaging today target **Windows**; the stack (Tauri + FastAPI + SPA) is intended to stay cross-platform, with **macOS** support planned.

## Features

- **Copy** — transfer media into `camera/year/month` or `year/month` folders
- **Sort** — reorganize existing libraries with rename / extension rules
- **Deduplicate** — match by name, size, date, or SHA-256 hash
- **Metadata** — edit EXIF fields and file timestamps for a single file
- **Settings** — language (ru/en), theme, media-only filter, default paths

## Requirements

- [Python](https://www.python.org/) 3.9+ on `PATH` (`py` / `python` on Windows, `python3` on macOS/Linux)
- Optional but recommended: [ExifTool](https://exiftool.org/) on `PATH` (RAW / video camera & shoot date). On Windows: `winget install OliverBetz.ExifTool`
- For the desktop shell (optional): [Node.js](https://nodejs.org/) 18+, [Rust](https://rustup.rs/)

## Quick start (backend + browser)

**Windows:**

```bat
run.bat
```

**Any platform** (after creating a venv and installing `requirements.txt`):

```bash
python -m uvicorn app:app --host 127.0.0.1 --port 8765
```

Then open [http://127.0.0.1:8765](http://127.0.0.1:8765).

`run.bat` creates `.venv` on first launch and installs dependencies from `requirements.txt`.

## Desktop shell (Tauri)

```bash
npm install
npm run dev
```

Production build:

```bash
npm run build
```

On Windows, installers land in `src-tauri/target/release/bundle/{msi,nsis}/`. Bundle targets for macOS can be added when that platform is productized.

## Portable pack (Windows, self-contained)

Builds a folder you can copy anywhere (USB, another PC). Includes `MediaFlow.exe`, `README.txt`, and a private `runtime\` with embeddable Python + dependencies — **no system Python install required**.

```bat
npm install
npm run pack:portable
```

Output: `dist\MediaFlow-portable\`

Optional: `powershell -ExecutionPolicy Bypass -File scripts\pack-portable.ps1 -SkipBuild` if `MediaFlow.exe` is already built.

WebView2 Runtime must be present on the target PC (normal on Windows 10/11). ExifTool remains optional and external.

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
| `scripts/pack-portable.ps1` | Build self-contained portable folder (Windows) |
| `requirements.txt` | Python dependencies |

## Notes

- SMB destination is disabled in the MVP on all platforms.
- ExifTool is an **external** tool; it is not bundled. Without it, RAW/video may fall back to `mtime` and `camera=Unknown`.
- MPEG Program Stream files (`.mpg` / `.mpeg`): embedded EXIF cannot be written by ExifTool; file timestamps can still be edited.

## License

[MIT](LICENSE) © 2026 Valerii Korobeinikov

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
