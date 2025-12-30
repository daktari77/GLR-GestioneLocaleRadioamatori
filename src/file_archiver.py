# -*- coding: utf-8 -*-
"""Small helper to archive files into managed folders using the same naming convention.

Naming convention: <hex token> + original extension (lowercased).

By default the token is 10 hex chars (historical behavior for member documents).
Some areas (e.g. section documents) may use a different length to distinguish.
"""

from __future__ import annotations

import secrets
import shutil
from pathlib import Path


def _hex_token(*, length: int) -> str:
    if length < 1:
        length = 1
    # token_hex(n) yields 2*n hex chars
    nbytes = max(1, (length + 1) // 2)
    return secrets.token_hex(nbytes)[:length]


def unique_hex_filename(directory: Path, extension: str, length: int = 10) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    ext = (extension or "").lower()
    while True:
        token = _hex_token(length=length)
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
