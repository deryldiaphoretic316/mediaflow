import asyncio
import hashlib
import json
import os
import platform
import re
import shutil
import string
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

import aiofiles
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# Load .env file
def load_env():
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip())

load_env()

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# RD-028: surface the missing-ExifTool case in the UI log.
# Pillow cannot read EXIF from RAW (CR2/CR3/NEF/ARW/DNG/ORF/RW2) or video
# (MOV/MP4/AVI/MTS/M4V/MPG); without ExifTool such files silently resolve to
# camera="Unknown" and date_taken=None (mtime fallback). This flag is consumed
# by copy_files/sort_files to emit an `info` SSE event at start of each run.
EXIFTOOL_AVAILABLE = shutil.which("exiftool") is not None
EXIFTOOL_MISSING_MESSAGE = (
    "ExifTool not found on PATH. Camera detection for RAW (CR2/CR3/NEF/ARW/DNG/ORF/RW2) "
    "and video (MOV/MP4/AVI/MTS/M4V/MPG) is unavailable; such files will be classified as "
    "camera='Unknown' and dated by file mtime. Install ExifTool from https://exiftool.org/ "
    "(or `winget install OliverBetz.ExifTool`) and restart the app."
)

app = FastAPI(title="MediaFlow")

SETTINGS_FILE = Path(__file__).parent / "settings.json"
SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".heic", ".heif",
    ".raw", ".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2",
    ".mov", ".mp4", ".avi", ".mts", ".m4v", ".mpg",
}
DEFAULT_SELECTED_EXTENSIONS = sorted(SUPPORTED_EXTENSIONS)

# ExifTool reads MPEG PS (.mpg/.mpeg) but cannot write metadata into the file.
EXIF_WRITE_UNSUPPORTED_EXTENSIONS = {".mpg", ".mpeg"}

SKIP_FILES = {".ds_store", "thumbs.db"}
SKIP_PREFIXES = {"._", "."}


def should_skip_file(path: Path) -> bool:
    """Check if file should be skipped (macOS artifacts, temp files, etc)."""
    name = path.name.lower()
    if name in SKIP_FILES:
        return True
    for prefix in SKIP_PREFIXES:
        if name.startswith(prefix):
            return True
    return False

DEFAULT_SETTINGS = {
    "source_path": "",
    "destination_path": "",
    "destination_smb": {
        "enabled": False,
        "server": "",
        "share": "",
        "username": "",
        "mount_point": "",
    },
    "duplicate_handling": "skip",  # skip, rename, overwrite
    "operation_mode": "copy",  # copy, move
    "folder_structure": "camera/year/month",  # camera/year/month or year/month
    "selected_extensions": DEFAULT_SELECTED_EXTENSIONS,
    "sort": {
        "source_path": "",
        "destination_path": "",
        "duplicates_path": "",
        "unsortable_path": "",
        "folder_structure": "camera/year/month",  # camera/year/month or year/month
        "selected_extensions": DEFAULT_SELECTED_EXTENSIONS,
        "rename_mode": "original",  # original, lowercase, original_plus_number
        "jpeg_to_jpg": False,  # applied before extension case rewrite
        "extension_mode": "lowercase",  # lowercase, uppercase
        "operation_mode": "copy",  # copy, move
    },
    "dedup": {
        "source_path": "",
        "destination_path": "",
        "duplicates_path": "",
        "selected_extensions": DEFAULT_SELECTED_EXTENSIONS,
        "match_mode": "name",  # name, name_date, name_size, hash
        "action_mode": "delete",  # delete, rename, move_to_duplicates
        "dry_run": False,
    },
    "preferences": {
        "language": "ru",  # ru, en
        "theme": "dark",  # dark, light
        "media_only_files": True,
        "default_paths": {
            "copy_source": "",
            "copy_destination": "",
            "sort_source": "",
            "sort_destination": "",
            "sort_duplicates": "",
            "sort_unsortable": "",
            "dedup_source": "",
            "dedup_destination": "",
            "dedup_duplicates": "",
        },
    },
}


# ─── Settings ────────────────────────────────────────────────────────────────

def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE) as f:
            saved = json.load(f)
        # merge with defaults so new keys always present
        merged = {**DEFAULT_SETTINGS, **saved}
        # migrate old "smb" to "destination_smb" if needed
        if "smb" in saved and "destination_smb" not in saved:
            merged["destination_smb"] = saved["smb"]
        # ensure destination_smb has all required keys
        merged["destination_smb"] = {**DEFAULT_SETTINGS["destination_smb"], **merged.get("destination_smb", {})}
        merged["sort"] = {**DEFAULT_SETTINGS["sort"], **merged.get("sort", {})}
        merged["dedup"] = {**DEFAULT_SETTINGS["dedup"], **merged.get("dedup", {})}
        merged["preferences"] = {**DEFAULT_SETTINGS["preferences"], **merged.get("preferences", {})}
        merged["preferences"]["default_paths"] = {
            **DEFAULT_SETTINGS["preferences"]["default_paths"],
            **merged["preferences"].get("default_paths", {}),
        }
        return merged
    return dict(DEFAULT_SETTINGS)


def save_settings(data: dict):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def normalize_selected_extensions(selected: object, allowed_extensions: Optional[set[str]] = None) -> set[str]:
    """Normalize selected extensions from settings to a valid set."""
    if not isinstance(selected, list):
        return set(DEFAULT_SELECTED_EXTENSIONS if allowed_extensions is None else sorted(allowed_extensions))

    normalized: set[str] = set()
    for value in selected:
        if not isinstance(value, str):
            continue
        ext = value.strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        if allowed_extensions is None:
            allowed = SUPPORTED_EXTENSIONS
        else:
            allowed = allowed_extensions
        if ext in allowed:
            normalized.add(ext)

    return normalized


def list_source_extensions(source: str, media_only: bool = True) -> list[str]:
    """Return sorted extensions that exist in source folder."""
    source_path = Path(source.strip()) if isinstance(source, str) else Path("")
    if not source_path.exists() or not source_path.is_dir():
        return []

    found: set[str] = set()
    for p in source_path.rglob("*"):
        if not p.is_file() or should_skip_file(p):
            continue
        ext = p.suffix.lower()
        if media_only:
            if ext in SUPPORTED_EXTENSIONS:
                found.add(ext)
        elif ext:
            found.add(ext)
    return sorted(found)


def get_source_summary(source: str, media_only: bool = True) -> dict:
    """Return summary for source folder scan."""
    source_path = Path(source.strip()) if isinstance(source, str) else Path("")
    if not source_path.exists() or not source_path.is_dir():
        return {"exists": False, "total_files": 0, "matched_files": 0, "extensions": []}

    total_files = 0
    matched_files = 0
    found: set[str] = set()
    for p in source_path.rglob("*"):
        if not p.is_file() or should_skip_file(p):
            continue
        total_files += 1
        ext = p.suffix.lower()
        if not ext:
            continue
        if media_only:
            if ext in SUPPORTED_EXTENSIONS:
                matched_files += 1
                found.add(ext)
        else:
            matched_files += 1
            found.add(ext)

    return {
        "exists": True,
        "total_files": total_files,
        "matched_files": matched_files,
        "extensions": sorted(found),
    }


# ─── EXIF helpers ─────────────────────────────────────────────────────────────

def get_exif_data(path: Path) -> dict:
    """Return dict with keys: camera, date_taken."""
    result = {"camera": "Unknown", "date_taken": None}

    # Try exiftool first (works with RAW files)
    try:
        proc = subprocess.run(
            ["exiftool", "-Make", "-Model", "-DateTimeOriginal", "-s", "-n", str(path)],
            capture_output=True, text=True, timeout=2
        )
        if proc.returncode == 0:
            lines = proc.stdout.strip().split("\n")
            data = {}
            for line in lines:
                if ":" in line:
                    key, val = line.split(":", 1)
                    data[key.strip()] = val.strip()

            make = data.get("Make", "").strip()
            model = data.get("Model", "").strip()
            if make and model:
                if model.lower().startswith(make.lower()):
                    result["camera"] = model
                else:
                    result["camera"] = f"{make} {model}"
            elif model:
                result["camera"] = model
            elif make:
                result["camera"] = make

            # RD-029: ExifTool's `-n` flag suppresses *print conversion*, but for
            # DateTimeOriginal there is no print conversion to suppress — the raw
            # value is the EXIF date string "YYYY:MM:DD HH:MM:SS", not a Unix
            # timestamp. The macOS source used `datetime.fromtimestamp(int(dt_str))`
            # which raises ValueError on every real file, silently fell back to
            # mtime, and produced wrong destination folders. Parse with strptime
            # to match the PIL branch below.
            dt_str = data.get("DateTimeOriginal")
            if dt_str:
                try:
                    result["date_taken"] = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
                except (ValueError, TypeError):
                    pass
            return result
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback to PIL for standard formats
    if not PIL_AVAILABLE:
        return result
    try:
        img = Image.open(path)
        exif_data = img._getexif()  # type: ignore[attr-defined]
        if not exif_data:
            return result
        tag_map = {TAGS.get(k, k): v for k, v in exif_data.items()}

        make = tag_map.get("Make", "").strip().rstrip("\x00")
        model = tag_map.get("Model", "").strip().rstrip("\x00")
        if make and model:
            if model.lower().startswith(make.lower()):
                result["camera"] = model
            else:
                result["camera"] = f"{make} {model}"
        elif model:
            result["camera"] = model
        elif make:
            result["camera"] = make

        for tag in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
            dt_str = tag_map.get(tag)
            if dt_str:
                try:
                    result["date_taken"] = datetime.strptime(str(dt_str), "%Y:%m:%d %H:%M:%S")
                    break
                except ValueError:
                    pass
    except Exception:
        pass
    return result


def get_file_date(path: Path, exif: dict) -> datetime:
    if exif.get("date_taken"):
        return exif["date_taken"]
    mtime = path.stat().st_mtime
    return datetime.fromtimestamp(mtime)


def exif_write_block_reason(path: Path) -> Optional[str]:
    """Return a stable reason code when embedded EXIF cannot be written for this file."""
    if path.suffix.lower() in EXIF_WRITE_UNSUPPORTED_EXTENSIONS:
        return "mpeg_ps_unsupported"
    return None


def exif_tags_writable(path: Path) -> bool:
    return exif_write_block_reason(path) is None


def resolve_safe_file_path(path_str: str) -> Path:
    """Validate an absolute path to an existing regular file."""
    raw = (path_str or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Path is required")
    path = Path(raw)
    if not path.is_absolute():
        raise HTTPException(status_code=400, detail="Path must be absolute")
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return path


def _parse_user_datetime(value: object) -> Optional[datetime]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise HTTPException(status_code=400, detail=f"Invalid datetime: {text}")


def _format_exif_datetime(dt: datetime) -> str:
    return dt.strftime("%Y:%m:%d %H:%M:%S")


def _format_datetime_local(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


def _read_exif_editable(path: Path) -> dict[str, str]:
    fields = {
        "make": "",
        "model": "",
        "date_time_original": "",
        "artist": "",
        "image_description": "",
    }
    if EXIFTOOL_AVAILABLE:
        try:
            proc = subprocess.run(
                [
                    "exiftool",
                    "-json",
                    "-Make",
                    "-Model",
                    "-DateTimeOriginal",
                    "-Artist",
                    "-ImageDescription",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                payload = json.loads(proc.stdout)
                if payload and isinstance(payload, list):
                    row = payload[0]
                    fields["make"] = str(row.get("Make", "") or "")
                    fields["model"] = str(row.get("Model", "") or "")
                    fields["artist"] = str(row.get("Artist", "") or "")
                    fields["image_description"] = str(row.get("ImageDescription", "") or "")
                    dto = row.get("DateTimeOriginal")
                    if dto:
                        try:
                            parsed = datetime.strptime(str(dto), "%Y:%m:%d %H:%M:%S")
                            fields["date_time_original"] = _format_datetime_local(parsed)
                        except ValueError:
                            fields["date_time_original"] = str(dto)
                return fields
        except (json.JSONDecodeError, subprocess.TimeoutExpired, OSError):
            pass

    if not PIL_AVAILABLE:
        return fields
    try:
        img = Image.open(path)
        exif_data = img._getexif()  # type: ignore[attr-defined]
        if not exif_data:
            return fields
        tag_map = {TAGS.get(k, k): v for k, v in exif_data.items()}
        fields["make"] = str(tag_map.get("Make", "") or "").strip().rstrip("\x00")
        fields["model"] = str(tag_map.get("Model", "") or "").strip().rstrip("\x00")
        fields["artist"] = str(tag_map.get("Artist", "") or "").strip().rstrip("\x00")
        fields["image_description"] = str(tag_map.get("ImageDescription", "") or "").strip().rstrip("\x00")
        for tag in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
            dt_str = tag_map.get(tag)
            if dt_str:
                try:
                    parsed = datetime.strptime(str(dt_str), "%Y:%m:%d %H:%M:%S")
                    fields["date_time_original"] = _format_datetime_local(parsed)
                    break
                except ValueError:
                    pass
    except Exception:
        pass
    return fields


def _read_file_times(path: Path) -> dict[str, str]:
    stat = path.stat()
    created_ts = stat.st_ctime if platform.system() == "Windows" else stat.st_mtime
    return {
        "created": _format_datetime_local(datetime.fromtimestamp(created_ts)),
        "modified": _format_datetime_local(datetime.fromtimestamp(stat.st_mtime)),
        "accessed": _format_datetime_local(datetime.fromtimestamp(stat.st_atime)),
    }


def read_file_metadata(path_str: str) -> dict:
    path = resolve_safe_file_path(path_str)
    block_reason = exif_write_block_reason(path)
    return {
        "path": str(path),
        "name": path.name,
        "exiftool_available": EXIFTOOL_AVAILABLE,
        "exif_writable": EXIFTOOL_AVAILABLE and block_reason is None,
        "exif_block_reason": block_reason or "",
        "exif": _read_exif_editable(path),
        "times": _read_file_times(path),
    }


def _set_windows_file_times(
    path: Path,
    created: Optional[datetime],
    accessed: Optional[datetime],
    modified: Optional[datetime],
) -> None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    FILE_WRITE_ATTRIBUTES = 0x0100
    OPEN_EXISTING = 3
    FILE_FLAG_BACKUP_SEMANTICS = 0x02000000

    class FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

    def to_filetime(dt: datetime) -> FILETIME:
        ft = int((dt.timestamp() + 11644473600) * 10_000_000)
        return FILETIME(ft & 0xFFFFFFFF, ft >> 32)

    handle = kernel32.CreateFileW(
        str(path),
        FILE_WRITE_ATTRIBUTES,
        0,
        None,
        OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS,
        None,
    )
    if handle in (-1, 0xFFFFFFFF):
        raise OSError(ctypes.get_last_error(), "CreateFileW failed")

    try:
        c_ptr = ctypes.byref(to_filetime(created)) if created else None
        a_ptr = ctypes.byref(to_filetime(accessed)) if accessed else None
        m_ptr = ctypes.byref(to_filetime(modified)) if modified else None
        if not kernel32.SetFileTime(handle, c_ptr, a_ptr, m_ptr):
            raise OSError(ctypes.get_last_error(), "SetFileTime failed")
    finally:
        kernel32.CloseHandle(handle)


def apply_file_times(
    path: Path,
    created: Optional[datetime],
    modified: Optional[datetime],
    accessed: Optional[datetime],
) -> None:
    stat = path.stat()
    at = accessed if accessed is not None else datetime.fromtimestamp(stat.st_atime)
    mt = modified if modified is not None else datetime.fromtimestamp(stat.st_mtime)
    if platform.system() == "Windows":
        ct = created if created is not None else datetime.fromtimestamp(stat.st_ctime)
        _set_windows_file_times(path, ct, at, mt)
    else:
        os.utime(path, (at.timestamp(), mt.timestamp()))


def _write_exif_editable(path: Path, exif: dict[str, Any]) -> list[str]:
    if not EXIFTOOL_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="ExifTool is required to write EXIF metadata. Install it and restart the app.",
        )
    args = ["exiftool", "-overwrite_original"]
    mapping = {
        "make": "Make",
        "model": "Model",
        "artist": "Artist",
        "image_description": "ImageDescription",
    }
    for key, tag in mapping.items():
        if key in exif:
            args.append(f"-{tag}={exif.get(key) or ''}")
    if "date_time_original" in exif:
        raw = (exif.get("date_time_original") or "").strip()
        if raw:
            dt = _parse_user_datetime(raw)
            if dt is None:
                raise HTTPException(status_code=400, detail="DateTimeOriginal is empty")
            args.append(f"-DateTimeOriginal={_format_exif_datetime(dt)}")
        else:
            args.append("-DateTimeOriginal=")
    args.append(str(path))
    proc = subprocess.run(args, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout or "ExifTool failed").strip()
        raise HTTPException(status_code=500, detail=message)
    return [line for line in (proc.stdout or "").splitlines() if line.strip()]


def write_file_metadata(body: dict) -> dict:
    path_str = body.get("path", "")
    path = resolve_safe_file_path(path_str)
    warnings: list[str] = []
    exif_log: list[str] = []

    exif = body.get("exif")
    block_reason = exif_write_block_reason(path)
    if isinstance(exif, dict) and exif:
        if block_reason:
            warnings.append(
                "Embedded EXIF was not written: ExifTool does not support writing "
                f"{path.suffix.lower()} files. File dates were still updated if requested."
            )
        elif EXIFTOOL_AVAILABLE:
            exif_log = _write_exif_editable(path, exif)
        else:
            warnings.append("EXIF was not written (ExifTool is required).")

    times = body.get("times")
    if isinstance(times, dict) and times:
        created = _parse_user_datetime(times.get("created"))
        modified = _parse_user_datetime(times.get("modified"))
        accessed = _parse_user_datetime(times.get("accessed"))
        apply_file_times(path, created, modified, accessed)

    if platform.system() != "Windows" and isinstance(times, dict) and times.get("created"):
        warnings.append("On this OS, creation time cannot be set separately; modified time was updated.")

    return {
        "status": "ok",
        "path": str(path),
        "exif_log": exif_log,
        "warnings": warnings,
        "metadata": read_file_metadata(str(path)),
    }


def sanitize_folder_name(name: str) -> str:
    """Remove characters that are problematic in folder names."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    return name.strip(" .")[:64] or "Unknown"


# ─── SMB mounting ─────────────────────────────────────────────────────────────

def ensure_smb_mounted(smb: dict) -> str:
    """Mount SMB share if not already mounted. Returns mount point path."""
    mount_point = smb.get("mount_point", "").strip()
    if not mount_point:
        raise ValueError("SMB mount point is not configured")

    mp = Path(mount_point)
    mp.mkdir(parents=True, exist_ok=True)

    # check if already mounted
    try:
        result = subprocess.run(["mount"], capture_output=True, text=True)
        if mount_point in result.stdout:
            return mount_point
    except Exception:
        pass

    server = smb.get("server", "").strip()
    share = smb.get("share", "").strip()
    username = smb.get("username", "").strip()
    # Try to get password from env first, then from config
    password = os.environ.get("SMB_PASSWORD", smb.get("password", ""))

    if not server or not share:
        raise ValueError("SMB server or share is not configured")

    system = platform.system()

    if system == "Darwin":
        # macOS: mount_smbfs //user:pass@server/share /mount/point
        if username and password:
            url = f"//{username}:{password}@{server}/{share}"
        elif username:
            url = f"//{username}@{server}/{share}"
        else:
            url = f"//{server}/{share}"
        cmd = ["mount_smbfs", url, mount_point]
    elif system == "Linux":
        # Linux: mount -t cifs //server/share /mount/point -o user=...,pass=...
        opts = f"username={username},password={password}" if username else "guest"
        cmd = ["sudo", "mount", "-t", "cifs", f"//{server}/{share}", mount_point, "-o", opts]
    else:
        raise OSError(f"Unsupported OS for SMB mounting: {system}")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise OSError(f"SMB mount failed: {proc.stderr.strip()}")

    return mount_point


# ─── Copy engine ──────────────────────────────────────────────────────────────

def build_dest_path(dest_root: Path, camera: str, date: datetime, folder_structure: str) -> Path:
    year = date.strftime("%Y")
    month = date.strftime("%m")
    cam = sanitize_folder_name(camera)

    if folder_structure == "year/month":
        return dest_root / year / month
    else:  # camera/year/month (default)
        return dest_root / cam / year / month


def resolve_duplicate(dest_file: Path, handling: str) -> Optional[Path]:
    """Return final destination path or None to skip."""
    if not dest_file.exists():
        return dest_file
    if handling == "overwrite":
        return dest_file
    if handling == "skip":
        return None
    # rename: add _1, _2, ...
    stem = dest_file.stem
    suffix = dest_file.suffix
    parent = dest_file.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def next_available_file_path(path: Path) -> Path:
    """Return a non-existing file path by adding _1, _2, ... suffix."""
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def apply_sorting_name_rules(
    src_file: Path,
    rename_mode: str,
    extension_mode: str,
    index: int,
    jpeg_to_jpg: bool = False,
) -> str:
    stem = src_file.stem
    suffix = src_file.suffix

    if rename_mode == "lowercase":
        stem = stem.lower()
    elif rename_mode == "original_plus_number":
        stem = f"{stem}_{index:04d}"

    # JPEG→JPG runs before case rewrite so the result follows lowercase/uppercase.
    if jpeg_to_jpg and suffix.lower() == ".jpeg":
        suffix = ".jpg"

    if extension_mode == "uppercase":
        suffix = suffix.upper()
    else:
        suffix = suffix.lower()

    return f"{stem}{suffix}"


def get_content_hash(path: Path) -> str:
    """Calculate SHA-256 hash of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_duplicate_key(path: Path, match_mode: str, hash_cache: dict[Path, str]) -> str:
    stat = path.stat()
    name = path.name.lower()

    if match_mode == "name_date":
        return f"{name}|{int(stat.st_mtime)}"
    if match_mode == "name_size":
        return f"{name}|{stat.st_size}"
    if match_mode == "hash":
        if path not in hash_cache:
            hash_cache[path] = get_content_hash(path)
        return hash_cache[path]
    return name


def duplicate_name_penalty(stem: str) -> int:
    """Higher score = name looks more like an auto-generated duplicate copy."""
    lower = stem.lower()
    penalty = 0
    if re.search(r"\(\d+\)$", stem):
        penalty += 30
    if re.search(r"(?:^|[\s_\-])(copy|копия)(?:[\s_\-]|\d*|$)", lower):
        penalty += 40
    if re.search(r"\bduplicate\b", lower):
        penalty += 40
    if re.search(r"(?:^|[\s_\-])dup(?:[\s_\-]|$)", lower):
        penalty += 25
    if re.search(r"[\s_\-]copy\s*\d*$", lower):
        penalty += 40
    return penalty


def duplicate_keep_sort_key(path: Path) -> tuple[int, int, str]:
    """Sort key for picking the keeper: lowest penalty, then shorter stem, then path."""
    stem = path.stem
    return (duplicate_name_penalty(stem), len(stem), str(path).lower())


def pick_duplicate_keeper(files: list[Path]) -> tuple[Path, list[Path]]:
    """Return (keeper, duplicates_to_process) for a group of matching files."""
    if not files:
        raise ValueError("files must not be empty")
    if len(files) == 1:
        return files[0], []
    ordered = sorted(files, key=duplicate_keep_sort_key)
    keeper = ordered[0]
    return keeper, [p for p in files if p != keeper]


async def copy_files(settings: dict) -> AsyncGenerator[str, None]:
    """Async generator that yields SSE-formatted lines."""

    def sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    source = settings.get("source_path", "").strip()
    destination = settings.get("destination_path", "").strip()
    smb_cfg = settings.get("destination_smb", {})
    media_only = settings.get("preferences", {}).get("media_only_files", True)
    allowed_extensions = set(SUPPORTED_EXTENSIONS) if media_only else set(list_source_extensions(source, media_only=False))
    selected_extensions = normalize_selected_extensions(settings.get("selected_extensions"), allowed_extensions=allowed_extensions)

    if not source or not destination:
        yield sse("error", {"message": "Source or destination path is not set"})
        return

    if not selected_extensions:
        yield sse("error", {"message": "No file types selected for copying"})
        return

    # SMB is intentionally disabled for MVP simplification.
    # Keep this block commented for quick restore later.
    # if smb_cfg.get("enabled"):
    #     try:
    #         mount_point = ensure_smb_mounted(smb_cfg)
    #         destination = mount_point  # use mount point as destination
    #         yield sse("info", {"message": f"SMB mounted at {mount_point}"})
    #     except Exception as e:
    #         yield sse("error", {"message": f"SMB mount failed: {e}"})
    #         return

    src_path = Path(source)
    dst_path = Path(destination)

    if not src_path.exists():
        yield sse("error", {"message": f"Source path does not exist: {source}"})
        return

    # collect files
    files = [
        p for p in src_path.rglob("*")
        if p.is_file() and p.suffix.lower() in selected_extensions and not should_skip_file(p)
    ]

    if not files:
        yield sse("done", {"message": "No supported files found in source", "copied": 0, "skipped": 0, "total": 0})
        return

    total = len(files)
    yield sse("start", {"total": total})

    if not EXIFTOOL_AVAILABLE:
        yield sse("info", {"message": EXIFTOOL_MISSING_MESSAGE})

    copied = skipped = errors = 0
    folder_structure = settings.get("folder_structure", "camera/year/month")
    duplicate_handling = settings.get("duplicate_handling", "skip")
    operation_mode = settings.get("operation_mode", "copy")
    if operation_mode not in {"copy", "move"}:
        operation_mode = "copy"

    for i, src_file in enumerate(files, 1):
        await asyncio.sleep(0)  # yield control

        try:
            exif = get_exif_data(src_file)
            date = get_file_date(src_file, exif)
            camera = exif.get("camera", "Unknown")

            dest_dir = build_dest_path(dst_path, camera, date, folder_structure)
            dest_dir.mkdir(parents=True, exist_ok=True)

            dest_file = dest_dir / src_file.name
            final_dest = resolve_duplicate(dest_file, duplicate_handling)

            if final_dest is None:
                skipped += 1
                yield sse("progress", {
                    "current": i, "total": total,
                    "file": src_file.name,
                    "status": "skipped",
                    "copied": copied, "skipped": skipped,
                })
                continue

            if operation_mode == "move":
                # Ensure overwrite works consistently across filesystems.
                if duplicate_handling == "overwrite" and final_dest.exists():
                    await asyncio.to_thread(final_dest.unlink)
                await asyncio.to_thread(shutil.move, str(src_file), str(final_dest))
            else:
                await asyncio.to_thread(shutil.copy2, src_file, final_dest)
            copied += 1
            yield sse("progress", {
                "current": i, "total": total,
                "file": src_file.name,
                "dest": str(final_dest.relative_to(dst_path)),
                "camera": camera,
                "operation": operation_mode,
                "status": "copied",
                "copied": copied, "skipped": skipped,
            })

        except Exception as e:
            errors += 1
            yield sse("progress", {
                "current": i, "total": total,
                "file": src_file.name,
                "status": "error",
                "error": str(e),
                "copied": copied, "skipped": skipped,
            })

    yield sse("done", {
        "message": "Copy complete",
        "total": total,
        "copied": copied,
        "skipped": skipped,
        "errors": errors,
    })


async def sort_files(settings: dict) -> AsyncGenerator[str, None]:
    """Sort files from source into destination using selected rules."""

    def sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    sort_cfg = settings.get("sort", {})
    source = sort_cfg.get("source_path", "").strip()
    destination = sort_cfg.get("destination_path", "").strip()
    duplicates = sort_cfg.get("duplicates_path", "").strip()
    unsortable = sort_cfg.get("unsortable_path", "").strip()

    folder_structure = sort_cfg.get("folder_structure", "camera/year/month")
    rename_mode = sort_cfg.get("rename_mode", "original")
    extension_mode = sort_cfg.get("extension_mode", "lowercase")
    # Legacy: extension_mode == "jpeg_to_jpg" meant only the JPEG→JPG rewrite.
    jpeg_to_jpg = bool(sort_cfg.get("jpeg_to_jpg", False)) or extension_mode == "jpeg_to_jpg"
    if extension_mode not in {"lowercase", "uppercase"}:
        extension_mode = "lowercase"
    operation_mode = sort_cfg.get("operation_mode", "copy")
    if operation_mode not in {"copy", "move"}:
        operation_mode = "copy"
    media_only = settings.get("preferences", {}).get("media_only_files", True)
    allowed_extensions = set(SUPPORTED_EXTENSIONS) if media_only else set(list_source_extensions(source, media_only=False))
    selected_extensions = normalize_selected_extensions(sort_cfg.get("selected_extensions"), allowed_extensions=allowed_extensions)

    if not source or not destination or not duplicates or not unsortable:
        yield sse("error", {"message": "Sort paths are not fully configured"})
        return
    if not selected_extensions:
        yield sse("error", {"message": "No file types selected for sorting"})
        return

    src_path = Path(source)
    dst_path = Path(destination)
    dup_path = Path(duplicates)
    uns_path = Path(unsortable)

    if not src_path.exists():
        yield sse("error", {"message": f"Source path does not exist: {source}"})
        return

    files = [
        p for p in src_path.rglob("*")
        if p.is_file() and p.suffix.lower() in selected_extensions and not should_skip_file(p)
    ]
    if not files:
        yield sse("done", {"message": "No supported files found in source", "sorted": 0, "duplicates": 0, "unsortable": 0, "errors": 0, "total": 0})
        return

    total = len(files)
    yield sse("start", {"total": total})

    if not EXIFTOOL_AVAILABLE:
        yield sse("info", {"message": EXIFTOOL_MISSING_MESSAGE})

    sorted_count = 0
    duplicates_count = 0
    unsortable_count = 0
    errors = 0

    for i, src_file in enumerate(files, 1):
        await asyncio.sleep(0)
        try:
            exif = get_exif_data(src_file)
            date = get_file_date(src_file, exif)
            camera = exif.get("camera", "Unknown")
            sortable = not (folder_structure == "camera/year/month" and camera == "Unknown")

            final_name = apply_sorting_name_rules(
                src_file, rename_mode, extension_mode, i, jpeg_to_jpg=jpeg_to_jpg
            )

            if not sortable:
                target_dir = uns_path
                target_dir.mkdir(parents=True, exist_ok=True)
                final_dest = next_available_file_path(target_dir / final_name)
                if operation_mode == "move":
                    await asyncio.to_thread(shutil.move, str(src_file), str(final_dest))
                else:
                    await asyncio.to_thread(shutil.copy2, src_file, final_dest)
                unsortable_count += 1
                yield sse("progress", {
                    "current": i,
                    "total": total,
                    "file": src_file.name,
                    "dest": str(final_dest),
                    "status": "unsortable",
                    "operation": operation_mode,
                    "sorted": sorted_count,
                    "duplicates": duplicates_count,
                    "unsortable": unsortable_count,
                    "errors": errors,
                })
                continue

            dest_dir = build_dest_path(dst_path, camera, date, folder_structure)
            dest_dir.mkdir(parents=True, exist_ok=True)
            primary_dest = dest_dir / final_name

            if primary_dest.exists():
                dup_path.mkdir(parents=True, exist_ok=True)
                duplicate_dest = next_available_file_path(dup_path / final_name)
                if operation_mode == "move":
                    await asyncio.to_thread(shutil.move, str(src_file), str(duplicate_dest))
                else:
                    await asyncio.to_thread(shutil.copy2, src_file, duplicate_dest)
                duplicates_count += 1
                yield sse("progress", {
                    "current": i,
                    "total": total,
                    "file": src_file.name,
                    "dest": str(duplicate_dest),
                    "status": "duplicate",
                    "operation": operation_mode,
                    "sorted": sorted_count,
                    "duplicates": duplicates_count,
                    "unsortable": unsortable_count,
                    "errors": errors,
                })
                continue

            if operation_mode == "move":
                await asyncio.to_thread(shutil.move, str(src_file), str(primary_dest))
            else:
                await asyncio.to_thread(shutil.copy2, src_file, primary_dest)
            sorted_count += 1
            yield sse("progress", {
                "current": i,
                "total": total,
                "file": src_file.name,
                "dest": str(primary_dest.relative_to(dst_path)),
                "camera": camera,
                "status": "sorted",
                "operation": operation_mode,
                "sorted": sorted_count,
                "duplicates": duplicates_count,
                "unsortable": unsortable_count,
                "errors": errors,
            })
        except Exception as e:
            errors += 1
            yield sse("progress", {
                "current": i,
                "total": total,
                "file": src_file.name,
                "status": "error",
                "error": str(e),
                "sorted": sorted_count,
                "duplicates": duplicates_count,
                "unsortable": unsortable_count,
                "errors": errors,
            })

    yield sse("done", {
        "message": "Sort complete",
        "total": total,
        "sorted": sorted_count,
        "duplicates": duplicates_count,
        "unsortable": unsortable_count,
        "errors": errors,
    })


async def deduplicate_files(settings: dict) -> AsyncGenerator[str, None]:
    """Find and process duplicates inside destination/source folder."""

    def sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    dedup_cfg = settings.get("dedup", {})
    source = dedup_cfg.get("source_path", "").strip()
    destination = dedup_cfg.get("destination_path", "").strip()
    duplicates_path = dedup_cfg.get("duplicates_path", "").strip()
    match_mode = dedup_cfg.get("match_mode", "name")
    action_mode = dedup_cfg.get("action_mode", "delete")
    dry_run = bool(dedup_cfg.get("dry_run", False))
    media_only = settings.get("preferences", {}).get("media_only_files", True)
    allowed_extensions = set(SUPPORTED_EXTENSIONS) if media_only else set(list_source_extensions(source, media_only=False))
    selected_extensions = normalize_selected_extensions(dedup_cfg.get("selected_extensions"), allowed_extensions=allowed_extensions)

    if not source:
        yield sse("error", {"message": "Dedup source path is not configured"})
        return
    if not selected_extensions:
        yield sse("error", {"message": "No file types selected for deduplication"})
        return
    if action_mode not in {"delete", "rename", "move_to_duplicates"}:
        yield sse("error", {"message": "Invalid dedup action mode"})
        return
    if match_mode not in {"name", "name_date", "name_size", "hash"}:
        yield sse("error", {"message": "Invalid dedup match mode"})
        return

    work_root = Path(destination) if destination else Path(source)
    if not work_root.exists() or not work_root.is_dir():
        yield sse("error", {"message": f"Working path does not exist: {work_root}"})
        return

    duplicates_root: Optional[Path] = None
    if action_mode == "move_to_duplicates":
        if not duplicates_path:
            yield sse("error", {"message": "Duplicates folder is required for move action"})
            return
        duplicates_root = Path(duplicates_path)
        duplicates_root.mkdir(parents=True, exist_ok=True)

    files = [
        p for p in work_root.rglob("*")
        if p.is_file() and p.suffix.lower() in selected_extensions and not should_skip_file(p)
    ]
    if not files:
        yield sse("done", {"message": "No supported files found", "total": 0, "duplicates": 0, "processed": 0, "errors": 0})
        return

    yield sse("start", {"total": len(files), "working_path": str(work_root)})

    groups: dict[str, list[Path]] = {}
    hash_cache: dict[Path, str] = {}
    scanned = 0
    errors = 0

    for idx, file_path in enumerate(sorted(files), 1):
        await asyncio.sleep(0)
        try:
            key = await asyncio.to_thread(build_duplicate_key, file_path, match_mode, hash_cache)
            groups.setdefault(key, []).append(file_path)
            scanned += 1
            yield sse("scan", {"current": idx, "total": len(files), "file": file_path.name})
        except Exception as e:
            errors += 1
            yield sse("progress", {"status": "error", "file": file_path.name, "error": str(e), "processed": 0, "duplicates": 0, "errors": errors})

    duplicate_candidates: list[Path] = []
    for same_files in groups.values():
        if len(same_files) > 1:
            _, to_process = pick_duplicate_keeper(same_files)
            duplicate_candidates.extend(to_process)

    processed = 0
    duplicate_count = len(duplicate_candidates)

    for idx, dup_file in enumerate(duplicate_candidates, 1):
        await asyncio.sleep(0)
        try:
            if action_mode == "delete":
                if not dry_run:
                    await asyncio.to_thread(dup_file.unlink)
                status = "deleted"
                result_path = ""
            elif action_mode == "rename":
                renamed_path = next_available_file_path(dup_file.with_name(f"{dup_file.stem}_dup{dup_file.suffix}"))
                if not dry_run:
                    await asyncio.to_thread(dup_file.rename, renamed_path)
                status = "renamed"
                result_path = str(renamed_path)
            else:  # move_to_duplicates
                assert duplicates_root is not None
                moved_path = next_available_file_path(duplicates_root / dup_file.name)
                if not dry_run:
                    await asyncio.to_thread(shutil.move, str(dup_file), str(moved_path))
                status = "moved"
                result_path = str(moved_path)

            processed += 1
            yield sse("progress", {
                "current": idx,
                "total": duplicate_count,
                "file": dup_file.name,
                "status": status,
                "dest": result_path,
                "dry_run": dry_run,
                "processed": processed,
                "duplicates": duplicate_count,
                "errors": errors,
            })
        except Exception as e:
            errors += 1
            yield sse("progress", {
                "current": idx,
                "total": duplicate_count,
                "file": dup_file.name,
                "status": "error",
                "error": str(e),
                "processed": processed,
                "duplicates": duplicate_count,
                "errors": errors,
            })

    yield sse("done", {
        "message": "Dedup preview complete" if dry_run else "Dedup complete",
        "total": scanned,
        "duplicates": duplicate_count,
        "processed": processed,
        "errors": errors,
        "dry_run": dry_run,
    })


# ─── API routes ───────────────────────────────────────────────────────────────

@app.get("/api/settings")
def api_get_settings():
    return load_settings()


@app.get("/api/file-types")
def api_file_types():
    return {"extensions": DEFAULT_SELECTED_EXTENSIONS}


@app.get("/api/source-file-types")
def api_source_file_types(path: str = "", media_only: bool = True):
    return {"extensions": list_source_extensions(path, media_only=media_only)}


@app.get("/api/source-summary")
def api_source_summary(path: str = "", media_only: bool = True):
    return get_source_summary(path, media_only=media_only)


@app.post("/api/settings")
def api_save_settings(body: dict):
    save_settings(body)
    return {"status": "ok"}


@app.get("/api/copy")
async def api_copy():
    settings = load_settings()

    async def generator():
        async for chunk in copy_files(settings):
            yield chunk

    return StreamingResponse(generator(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@app.get("/api/sort")
async def api_sort():
    settings = load_settings()

    async def generator():
        async for chunk in sort_files(settings):
            yield chunk

    return StreamingResponse(generator(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@app.get("/api/deduplicate")
async def api_deduplicate():
    settings = load_settings()

    async def generator():
        async for chunk in deduplicate_files(settings):
            yield chunk

    return StreamingResponse(generator(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


def _windows_browse_roots() -> list[dict]:
    """Return browse roots for Windows: drive letters + common user folders.

    See RD-013 (drive letters via ``string.ascii_uppercase`` + ``Path.exists``)
    and RD-014 (Desktop / Pictures / Downloads / Documents under USERPROFILE).
    """
    entries: list[dict] = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if Path(drive).exists():
            entries.append({"name": drive, "path": drive})

    user_profile = os.environ.get("USERPROFILE", "")
    if user_profile:
        for sub in ("Desktop", "Pictures", "Downloads", "Documents"):
            p = Path(user_profile) / sub
            if p.exists():
                entries.append({"name": f"~/{sub}", "path": str(p)})
    return entries


@app.get("/api/file-metadata")
def api_get_file_metadata(path: str = ""):
    return read_file_metadata(path)


@app.post("/api/file-metadata")
def api_save_file_metadata(body: dict):
    return write_file_metadata(body)


@app.get("/api/browse")
def api_browse(path: str = "", pick: str = "folder"):
    """List directories at the given path. pick=file also lists files in the folder."""
    try:
        if not path:
            system = platform.system()
            if system == "Darwin":
                roots = ["/Volumes", "/Users", "/tmp"]
                entries = [{"name": r, "path": r} for r in roots if Path(r).exists()]
            elif system == "Windows":
                # Windows-specific roots: drive letters + common user folders.
                # See RD-012, RD-013, RD-014 in roadmap.md.
                entries = _windows_browse_roots()
            else:
                roots = ["/media", "/mnt", "/home", "/tmp"]
                entries = [{"name": r, "path": r} for r in roots if Path(r).exists()]
            return {"path": "", "entries": entries}

        p = Path(path)
        if not p.exists() or not p.is_dir():
            raise HTTPException(status_code=404, detail="Path not found")

        entries: list[dict] = []
        for e in sorted(p.iterdir(), key=lambda x: x.name.lower()):
            if e.is_dir():
                entries.append({"name": e.name, "path": str(e), "type": "dir"})
            elif pick == "file" and e.is_file() and not should_skip_file(e):
                entries.append({"name": e.name, "path": str(e), "type": "file"})
        parent = str(p.parent) if p.parent != p else ""
        return {"path": str(p), "parent": parent, "entries": entries, "pick": pick}
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")


@app.get("/api/test-smb")
def api_test_smb():
    # SMB temporarily disabled for MVP.
    return {"status": "disabled", "message": "SMB is temporarily disabled in MVP"}


@app.get("/", response_class=HTMLResponse)
def root():
    html_path = Path(__file__).parent / "static" / "index.html"
    return html_path.read_text(encoding="utf-8")


# serve static files
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
