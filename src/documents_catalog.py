"""Member document type catalog.

Kept for backward compatibility.
The single source of truth for document types is now `document_types_catalog.py`.
"""

from __future__ import annotations

from typing import Iterable

from document_types_catalog import DOCUMENT_CATEGORIES, DEFAULT_DOCUMENT_CATEGORY
from document_types_catalog import ensure_member_document_type as ensure_category
from document_types_catalog import normalize_member_document_type as normalize_category
