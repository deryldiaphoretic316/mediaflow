# MediaFlow

**Desktop app for organizing photos and videos — copy, sort, deduplicate, and edit EXIF and file dates.**

Point it at a memory card or a folder: it files everything into `camera/year/month`, finds the duplicates, and repairs the dates the camera got wrong. Free and open source under the [MIT License](LICENSE).

## Download

Windows, portable — no installer and no system Python required:

**[MediaFlow-portable-0.1.0-win64.zip](https://github.com/vkgeorgia/mediaflow/releases/download/v0.1.0/MediaFlow-portable-0.1.0-win64.zip)** (~32 MB) — or pick it from the [Releases](https://github.com/vkgeorgia/mediaflow/releases) page.

Unpack it anywhere and run `MediaFlow.exe`. Keep the folder together: `runtime\`, `app.py` and `static\` must stay next to the executable.

Windows is the packaged platform today. The stack (Tauri + FastAPI + SPA) is cross-platform, and macOS packaging is planned.

## Features

- **Copy** — transfer media into `camera/year/month` or `year/month` folders
- **Sort** — reorganize existing libraries with rename / extension rules
- **Deduplicate** — match by name, size, date, or SHA-256 hash
- **Metadata** — edit EXIF fields and file timestamps for a single file
- **Settings** — language (ru/en), theme, media-only filter, default paths

## Requirements

Only for running from source or building; the portable pack needs none of it.

- [Python](https://www.python.org/) 3.9+ on `PATH` (`py` / `python` on Windows, `python3` on macOS/Linux)
- Optional but recommended: [ExifTool](https://exiftool.org/) on `PATH`, for camera and shoot dates on RAW and video (`winget install OliverBetz.ExifTool` on Windows)
- For the desktop shell: [Node.js](https://nodejs.org/) 18+ and [Rust](https://rustup.rs/)

## Run from source

On Windows:

```bat
run.bat
```

On any platform, after creating a venv and installing `requirements.txt`:

```bash
python -m uvicorn app:app --host 127.0.0.1 --port 8765
```

Then open [http://127.0.0.1:8765](http://127.0.0.1:8765). `run.bat` creates `.venv` on first launch and installs the dependencies for you.

## Desktop shell (Tauri)

```bash
npm install
npm run dev      # development
npm run build    # production build
```

On Windows the installers land in `src-tauri/target/release/bundle/{msi,nsis}/`. Bundle targets for macOS can be added when that platform is productized.

## Build the portable pack (Windows)

Produces a self-contained folder you can copy to a USB stick or another PC — `MediaFlow.exe`, `README.txt`, and a private `runtime\` with an embeddable Python and the dependencies.

```bat
npm install
npm run pack:portable
```

Output: `dist\MediaFlow-portable\`. Add `-SkipBuild` to reuse an existing executable:

```bat
powershell -ExecutionPolicy Bypass -File scripts\pack-portable.ps1 -SkipBuild
```

The target PC needs the WebView2 Runtime, which is standard on Windows 10 and 11. ExifTool stays optional and external.

## Configuration

Runtime settings live in `settings.json` next to `app.py` (gitignored). See `settings.example.json` for the schema and the defaults.

## Project layout

| Path | Role |
|------|------|
| `app.py` | FastAPI backend (REST + SSE) |
| `static/index.html` | Single-page UI (Alpine.js + Tailwind CDN) |
| `src-tauri/` | Tauri 2 desktop shell |
| `run.bat` | Windows dev launcher |
| `scripts/pack-portable.ps1` | Build the self-contained portable folder (Windows) |
| `requirements.txt` | Python dependencies |

## Notes

- SMB destinations are disabled in the MVP on all platforms.
- ExifTool is an **external** tool and is not bundled. Without it, RAW and video may fall back to `mtime` and `camera=Unknown`.
- MPEG Program Stream files (`.mpg` / `.mpeg`): ExifTool cannot write embedded EXIF for them; file timestamps can still be edited.

## Contributing

Bug reports and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) © 2026 Valerii Korobeinikov

## Author

[Valerii Korobeinikov](https://github.com/vkgeorgia), Enterprise Architect — [korobeinikov.consulting](https://korobeinikov.consulting/) · [LinkedIn](https://www.linkedin.com/in/valeriikorobeinikov/)
