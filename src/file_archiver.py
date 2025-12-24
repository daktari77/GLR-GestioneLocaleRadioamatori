# -*- coding: utf-8 -*-
"""Small helper to archive files into managed folders using the same naming convention.

Naming convention: 10-hex token + original extension (lowercased).
"""

from __future__ import annotations

import secrets
import shutil
from pathlib import Path


def unique_hex_filename(directory: Path, extension: str) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    ext = (extension or "").lower()
    while True:
        token = secrets.token_hex(5)  # 10 hex chars
        candidate = f"{token}{ext}"
        if not (directory / candidate).exists():
            return candidate


def archive_file(
    *,
    source_path: str | Path,
    target_dir: str | Path,
    keep_mtime: bool = True,
) -> tuple[str, str]:
    """Copy a file into target_dir using the standard naming convention.

    Returns:
        (absolute_dest_path, stored_filename)
    """
    src = Path(source_path).expanduser()
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"File non trovato: {source_path}")

    dst_dir = Path(target_dir).expanduser()
    dst_dir.mkdir(parents=True, exist_ok=True)

    stored_name = unique_hex_filename(dst_dir, src.suffix)
    dest = dst_dir / stored_name

    if keep_mtime:
        shutil.copy2(src, dest)
    else:
        shutil.copy(src, dest)

    return str(dest.resolve()), stored_name
