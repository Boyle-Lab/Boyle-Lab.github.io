from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_front_matter(path: Path) -> tuple[dict[str, Any], str]:
    """Return parsed Jekyll front matter and the remaining document body."""
    text = path.read_text(encoding="utf-8-sig")
    if not text.startswith("---"):
        raise AssertionError(f"{path.relative_to(ROOT)} has no YAML front matter")
    parts = text.split("---", 2)
    if len(parts) != 3:
        raise AssertionError(f"{path.relative_to(ROOT)} has malformed front matter")
    data = yaml.safe_load(parts[1]) or {}
    if not isinstance(data, dict):
        raise AssertionError(f"{path.relative_to(ROOT)} front matter is not a mapping")
    return data, parts[2].lstrip("\r\n")


def local_asset_path(value: str, *, default_root: str | None = None) -> Path | None:
    """Resolve a site-relative asset value; return None for external/Liquid URLs."""
    value = str(value or "").strip()
    if not value or "://" in value or "{{" in value or "{%" in value or value.startswith("mailto:"):
        return None
    if value.startswith("/"):
        return ROOT / value.lstrip("/")
    if default_root:
        return ROOT / default_root / value
    return ROOT / value
