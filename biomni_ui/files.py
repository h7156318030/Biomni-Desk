"""Locate and safely serve files the agent produced (figures, tables, reports)."""

from __future__ import annotations

from pathlib import Path

ALLOWED_EXT = {
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image", ".webp": "image", ".svg": "image",
    ".pdf": "pdf", ".csv": "table", ".tsv": "table", ".html": "html", ".txt": "text", ".json": "text",
    ".xlsx": "table", ".xls": "table", ".parquet": "table", ".md": "text", ".fasta": "text", ".fa": "text",
    ".fastq": "text", ".gz": "text", ".zip": "text", ".h5ad": "text", ".docx": "text", ".pptx": "text",
    ".mp4": "video", ".webm": "video", ".mov": "video",
}
MAX_UPLOAD_BYTES = 100 * 1024 * 1024


def resolve(candidate: str, roots: list[Path]) -> Path | None:
    """Return the real path of `candidate` if it exists inside one of `roots` and has an allowed type."""
    p = Path(candidate)
    options = [p] if p.is_absolute() else [r / p for r in roots]
    for opt in options:
        try:
            real = opt.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if real.is_file() and real.suffix.lower() in ALLOWED_EXT and is_inside(real, roots):
            return real
    return None


def is_inside(path: Path, roots: list[Path]) -> bool:
    for r in roots:
        try:
            path.relative_to(r.resolve())
            return True
        except ValueError:
            continue
    return False


def describe(path: Path) -> dict:
    st = path.stat()
    return {"name": path.name, "path": str(path), "kind": ALLOWED_EXT[path.suffix.lower()],
            "mtime": st.st_mtime, "size": st.st_size}


def safe_upload_name(filename: str) -> str:
    """The file name to store an upload under: a plain base name, allowed type only. Raises ValueError otherwise."""
    name = Path(filename.replace("\\", "/")).name.strip().strip(".")
    name = "".join(ch for ch in name if ch.isalnum() or ch in "._- ()+，,（）") or ""
    if not name or Path(name).suffix.lower() not in ALLOWED_EXT:
        raise ValueError("This file type is not supported. Allowed types: " + ", ".join(sorted(ALLOWED_EXT)))
    return name[:120]
