# Contributing to MediaFlow

Thanks for your interest in contributing.

## Development

1. Install Python 3.9+ and (optionally) ExifTool.
2. From the repo root:

```bat
run.bat
```

3. Open http://127.0.0.1:8765

For the Tauri shell: `npm install` then `npm run dev` (requires Rust).

## Guidelines

- Keep changes focused and small.
- Prefer parity with existing copy / sort / dedup behavior unless the change is intentional.
- Do not commit `settings.json`, `.venv/`, or local secrets.
- Match the language of the issue or PR discussion; UI strings should stay in both `ru` and `en` in `static/index.html`.

## Pull requests

- Describe **why** the change is needed.
- Note how you tested (browser via `run.bat` and/or Tauri).
- Include screenshots for UI changes when helpful.

## License

By contributing, you agree that your contributions are licensed under the MIT License (see [LICENSE](LICENSE)).
