"""Recursive unpack of the nested evidence tree - email -> zip -> workbook -> image.

Pure Python, deterministic, no model. Every leaf lands in the immutable
evidence store named by its SHA-256 (content-addressed, so re-ingest of the
same bytes is a no-op and hashes are stable by construction).
"""
from __future__ import annotations

import email
import email.policy
import hashlib
import io
import os
import shutil
import zipfile
from pathlib import Path

from iqr import config
from iqr.schemas.evidence_graph import EvidenceLeaf, LeafKind

_EXT_KIND: dict[str, LeafKind] = {
    ".docx": "docx", ".xlsx": "xlsx", ".xlsm": "xlsx", ".xlsb": "xlsb",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image",
    ".eml": "email", ".msg": "email", ".zip": "zip", ".pdf": "pdf",
    ".url": "link", ".lnk": "link",
}

MAX_DEPTH = 6  # the real packs nest ~3 deep; 6 is a hard safety bound
CHUNK = 4 * 1024 * 1024
BIG_FILE = 50_000_000  # above this, bytes are streamed and never held whole


def kind_of(name: str) -> LeafKind:
    return _EXT_KIND.get(Path(name).suffix.lower(), "other")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def store_blob(data: bytes) -> Path:
    """Immutable, content-addressed store. Never overwrite: same hash = same bytes."""
    config.ensure_dirs()
    path = config.EVIDENCE_STORE_DIR / sha256(data)
    if not path.exists():
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.rename(path)
    return path


def unpack_package(package_dir: Path) -> tuple[list[EvidenceLeaf], list[str]]:
    """Walk the package directory; recursively unpack emails and zips.

    Returns (leaves, errors): every leaf (containers included, so containment
    is auditable) sorted by logical_path for deterministic ordering, plus any
    corrupt-container errors - recorded, never swallowed.
    An empty package is refused outright: no evidence means nothing to
    validate, and a silent empty run must never look like a validation.
    """
    leaves: list[EvidenceLeaf] = []
    errors: list[str] = []
    for path in sorted(package_dir.rglob("*")):
        if path.is_file() and not path.name.startswith("."):
            rel = str(path.relative_to(package_dir))
            if path.stat().st_size > BIG_FILE:
                _ingest_path(path, rel, None, 0, leaves, errors)
            else:
                _ingest_bytes(path.read_bytes(), rel, None, 0, leaves, errors)
    if not leaves:
        raise ValueError(f"empty GRC package: no artifacts found in {package_dir}")
    leaves.sort(key=lambda l: l.logical_path)
    return leaves, errors


def _ingest_bytes(data: bytes, logical_path: str, parent_hash: str | None,
                  depth: int, out: list[EvidenceLeaf], errors: list[str]) -> str:
    if depth > MAX_DEPTH:
        raise ValueError(f"Evidence nesting exceeds {MAX_DEPTH} levels at {logical_path}")
    file_hash = sha256(data)
    stored = store_blob(data)
    kind = kind_of(logical_path)
    out.append(EvidenceLeaf(file_hash=file_hash, logical_path=logical_path, kind=kind,
                            size=len(data), parent_hash=parent_hash, stored_path=str(stored)))
    if kind == "zip":
        try:
            _unpack_zip(data, logical_path, file_hash, depth, out, errors)
        except zipfile.BadZipFile as e:
            errors.append(f"corrupt zip, children not extracted: {logical_path} ({e})")
    elif kind == "email" and logical_path.lower().endswith(".eml"):
        try:
            _unpack_eml_attachments(data, logical_path, file_hash, depth, out, errors)
        except Exception as e:
            errors.append(f"unreadable email attachments: {logical_path} ({e})")
    elif kind == "docx":
        try:
            _unpack_docx_embeddings(data, logical_path, file_hash, depth, out, errors)
        except Exception as e:
            errors.append(f"unreadable docx embeddings: {logical_path} ({e})")
    elif kind == "email" and logical_path.lower().endswith(".msg"):
        try:
            _unpack_msg_attachments(data, logical_path, file_hash, depth, out, errors)
        except Exception as e:
            errors.append(f"unreadable .msg attachments: {logical_path} ({e})")
    return file_hash


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def _store_from_file(src: Path, file_hash: str) -> Path:
    config.ensure_dirs()
    path = config.EVIDENCE_STORE_DIR / file_hash
    if not path.exists():
        tmp = path.with_suffix(".tmp")
        with open(src, "rb") as fi, open(tmp, "wb") as fo:
            shutil.copyfileobj(fi, fo, CHUNK)
        tmp.rename(path)
    return path


def _store_from_stream(fh) -> tuple[str, Path, int]:
    """Hash and store a readable stream in one chunked pass."""
    config.ensure_dirs()
    h = hashlib.sha256()
    size = 0
    tmp = config.EVIDENCE_STORE_DIR / f".stream-{os.getpid()}-{id(fh)}.tmp"
    with open(tmp, "wb") as fo:
        while True:
            chunk = fh.read(CHUNK)
            if not chunk:
                break
            h.update(chunk)
            size += len(chunk)
            fo.write(chunk)
    file_hash = h.hexdigest()
    final = config.EVIDENCE_STORE_DIR / file_hash
    if final.exists():
        tmp.unlink()
    else:
        tmp.rename(final)
    return file_hash, final, size


def _ingest_path(path: Path, logical_path: str, parent_hash: str | None,
                 depth: int, out: list[EvidenceLeaf], errors: list[str]) -> str:
    """Streaming ingest for large on-disk files - bytes never held whole."""
    if depth > MAX_DEPTH:
        raise ValueError(f"Evidence nesting exceeds {MAX_DEPTH} levels at {logical_path}")
    file_hash = _sha256_file(path)
    stored = _store_from_file(path, file_hash)
    kind = kind_of(logical_path)
    out.append(EvidenceLeaf(file_hash=file_hash, logical_path=logical_path, kind=kind,
                            size=path.stat().st_size, parent_hash=parent_hash,
                            stored_path=str(stored)))
    if kind in ("zip", "docx"):
        prefix = "word/embeddings/" if kind == "docx" else None
        try:
            _unpack_zip_streaming(stored, prefix, logical_path, file_hash, depth, out, errors)
        except zipfile.BadZipFile as e:
            errors.append(f"corrupt container, children not extracted: {logical_path} ({e})")
    elif kind == "email":
        # rare: a >50MB email - fall back to the in-memory handlers
        _ingest_bytes(path.read_bytes(), logical_path, parent_hash, depth, out, errors)
    return file_hash


def _unpack_zip_streaming(stored: Path, prefix: str | None, logical_path: str,
                          parent_hash: str, depth: int,
                          out: list[EvidenceLeaf], errors: list[str]) -> None:
    """Walk a zip container from its stored path; large entries stream to the
    store, small entries take the normal in-memory route."""
    with zipfile.ZipFile(stored) as zf:
        for info in sorted(zf.infolist(), key=lambda i: i.filename):
            name = info.filename
            if name.endswith("/") or (prefix and not name.startswith(prefix)):
                continue
            child_lp = f"{logical_path}!{name}"
            if info.file_size > BIG_FILE:
                if depth + 1 > MAX_DEPTH:
                    raise ValueError(f"Evidence nesting exceeds {MAX_DEPTH} levels at {child_lp}")
                with zf.open(name) as fh:
                    child_hash, child_stored, csize = _store_from_stream(fh)
                ckind = kind_of(name)
                out.append(EvidenceLeaf(file_hash=child_hash, logical_path=child_lp,
                                        kind=ckind, size=csize, parent_hash=parent_hash,
                                        stored_path=str(child_stored)))
                if ckind in ("zip", "docx"):
                    _unpack_zip_streaming(child_stored,
                                          "word/embeddings/" if ckind == "docx" else None,
                                          child_lp, child_hash, depth + 1, out, errors)
            else:
                child = zf.read(name)
                if child:
                    _ingest_bytes(child, child_lp, parent_hash, depth + 1, out, errors)


def _unpack_zip(data: bytes, logical_path: str, parent_hash: str,
                depth: int, out: list[EvidenceLeaf], errors: list[str] | None = None) -> None:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in sorted(zf.namelist()):
            if name.endswith("/"):
                continue
            child = zf.read(name)
            _ingest_bytes(child, f"{logical_path}!{name}", parent_hash, depth + 1, out, errors or [])


def _unpack_docx_embeddings(data: bytes, logical_path: str, parent_hash: str,
                            depth: int, out: list[EvidenceLeaf], errors: list[str] | None = None) -> None:
    """404 docs often embed the actual working papers as OLE objects."""
    import io
    import zipfile
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in zf.namelist():
            if name.startswith("word/embeddings/") and not name.endswith("/"):
                child = zf.read(name)
                if child:
                    _ingest_bytes(child, f"{logical_path}!{name}", parent_hash,
                                  depth + 1, out, errors or [])


def _unpack_msg_attachments(data: bytes, logical_path: str, parent_hash: str,
                            depth: int, out: list[EvidenceLeaf], errors: list[str] | None = None) -> None:
    """Outlook .msg: pull each attachment (workbooks, nested ZIPs) via extract-msg."""
    import tempfile
    import extract_msg
    with tempfile.NamedTemporaryFile(suffix=".msg", delete=True) as tf:
        tf.write(data)
        tf.flush()
        msg = extract_msg.openMsg(tf.name)
        try:
            for att in msg.attachments:
                payload = att.data
                name = att.longFilename or att.shortFilename or "attachment.bin"
                if isinstance(payload, bytes) and payload:
                    _ingest_bytes(payload, f"{logical_path}!{name}", parent_hash,
                                  depth + 1, out, errors or [])
        finally:
            msg.close()


def _unpack_eml_attachments(data: bytes, logical_path: str, parent_hash: str,
                            depth: int, out: list[EvidenceLeaf], errors: list[str] | None = None) -> None:
    msg = email.message_from_bytes(data, policy=email.policy.default)
    for part in msg.walk():
        filename = part.get_filename()
        if filename and part.get_content_disposition() == "attachment":
            payload = part.get_payload(decode=True)
            if payload:
                _ingest_bytes(payload, f"{logical_path}!{filename}", parent_hash, depth + 1, out, errors or [])
