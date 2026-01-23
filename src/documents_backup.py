# -*- coding: utf-8 -*-
"""
Incremental and full backup for documents (soci and section) with cloud mirroring.
"""
import os
import shutil
import hashlib
import json
from datetime import datetime
from pathlib import Path
from backup import _get_backup_repo_dir, _mirror_backup_to_repo

def hash_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

def collect_files(root_dir):
    files = []
    for base, _, filenames in os.walk(root_dir):
        for fn in filenames:
            full = os.path.join(base, fn)
            rel = os.path.relpath(full, root_dir)
            files.append((rel, full))
    return files

def load_manifest(manifest_path):
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_manifest(manifest_path, manifest):
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

def backup_documents(data_dir, backup_dir, mode='incremental'):
    """
    Esegue backup incrementale o full di data/documents e data/section_docs.
    mode: 'incremental' o 'full'
    """
    now = datetime.now().strftime('%Y%m%d_%H%M%S')
    label = f"{mode}_documents_{now}"
    dest_dir = os.path.join(backup_dir, label)
    os.makedirs(dest_dir, exist_ok=True)
    manifest_path = os.path.join(backup_dir, f"{label}_manifest.json")
    prev_manifest_path = os.path.join(backup_dir, 'last_documents_manifest.json')
    prev_manifest = load_manifest(prev_manifest_path)
    manifest = {}
    changed = 0
    for sub in ['documents', 'section_docs']:
        src_root = os.path.join(data_dir, sub)
        if not os.path.exists(src_root):
            continue
        for rel, full in collect_files(src_root):
            h = hash_file(full)
            manifest[f"{sub}/{rel}"] = h
            if mode == 'full' or prev_manifest.get(f"{sub}/{rel}") != h:
                # Copy only new/changed files (or all if full)
                dest_file = os.path.join(dest_dir, sub, rel)
                os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                shutil.copy2(full, dest_file)
                changed += 1
    save_manifest(manifest_path, manifest)
    save_manifest(prev_manifest_path, manifest)
    # Mirror to cloud if configured
    _mirror_backup_to_repo(dest_dir)
    _mirror_backup_to_repo(manifest_path)
    print(f"Backup {mode} completato: {changed} file copiati in {dest_dir}")
    return dest_dir, changed
