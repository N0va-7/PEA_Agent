from __future__ import annotations

import math
import mimetypes
from collections import Counter
from pathlib import PurePosixPath

from app.static_scan.models import FileProfile

OOXML_MARKERS = ("word/", "xl/", "ppt/", "[Content_Types].xml")
DANGEROUS_EXTENSIONS = {
    ".js",
    ".vbs",
    ".vbe",
    ".ps1",
    ".bat",
    ".cmd",
    ".hta",
    ".lnk",
    ".exe",
    ".dll",
    ".scr",
    ".com",
    ".jar",
    ".msi",
}
BENIGN_LEADING_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg", ".txt"}
MIME_GROUPS = {
    "office": {"application/msword", "application/vnd.openxmlformats-officedocument"},
    "pdf": {"application/pdf"},
    "archive": {"application/zip", "application/x-tar", "application/gzip"},
    "script": {"application/javascript", "text/html", "text/javascript", "text/vbscript"},
    "executable": {"application/x-msdownload", "application/x-dosexec"},
    "image": {"image/png", "image/jpeg", "image/gif"},
    "text": {"text/plain"},
}


def build_profile(
    *,
    filename: str,
    content: bytes,
    sha256: str,
    declared_mime: str | None,
    depth: int,
) -> FileProfile:
    return FileProfile(
        filename=filename,
        sha256=sha256,
        normalized_type=detect_type(filename, content),
        declared_mime=declared_mime,
        size_bytes=len(content),
        depth=depth,
        entropy=shannon_entropy(content[:65536]),
        looks_like_text=is_text_like(content),
        double_extension=has_double_extension(filename),
        declared_mime_group=map_declared_mime(declared_mime),
    )


def detect_type(filename: str, content: bytes) -> str:
    lowered = filename.lower()
    ext = PurePosixPath(lowered).suffix

    if content.startswith(b"%PDF"):
        return "pdf"
    if content.startswith(b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"):
        return "office"
    if content.startswith(b"PK\x03\x04"):
        if any(marker.encode("utf-8") in content for marker in OOXML_MARKERS):
            return "office"
        if ext in {".docx", ".docm", ".xlsx", ".xlsm", ".pptx", ".pptm"}:
            return "office"
        return "archive"
    if content.startswith(b"\x1f\x8b") or is_probable_tar(content):
        return "archive"
    if content.startswith(b"MZ") or content.startswith(b"\x7fELF") or content[:4] in {
        b"\xFE\xED\xFA\xCE",
        b"\xFE\xED\xFA\xCF",
        b"\xCF\xFA\xED\xFE",
        b"\xCE\xFA\xED\xFE",
    }:
        return "executable"
    if content.startswith(b"L\x00\x00\x00\x01\x14\x02\x00"):
        return "lnk"
    if content.startswith(b"\x89PNG\r\n\x1a\n") or content.startswith(b"\xff\xd8\xff") or content.startswith(b"GIF8"):
        return "image"
    if ext in DANGEROUS_EXTENSIONS or looks_like_script(content, ext):
        return "script"
    if is_text_like(content):
        return "text"
    return "unknown"


def map_declared_mime(declared_mime: str | None) -> str | None:
    if not declared_mime:
        return None
    for group, values in MIME_GROUPS.items():
        if any(declared_mime.startswith(value) for value in values):
            return group
    guessed, _ = mimetypes.guess_type(f"placeholder{PurePosixPath(declared_mime).suffix}")
    if guessed:
        for group, values in MIME_GROUPS.items():
            if guessed in values:
                return group
    return None


def has_double_extension(filename: str) -> bool:
    suffixes = [suffix.lower() for suffix in PurePosixPath(filename).suffixes]
    if len(suffixes) < 2:
        return False
    return suffixes[-1] in DANGEROUS_EXTENSIONS and suffixes[-2] in BENIGN_LEADING_EXTENSIONS


def safe_text(content: bytes) -> str:
    return content.decode("utf-8", errors="ignore")


def is_text_like(content: bytes) -> bool:
    if not content:
        return True
    sample = content[:2048]
    text_bytes = sum(byte in b"\t\n\r\f\b" or 32 <= byte <= 126 for byte in sample)
    return text_bytes / len(sample) > 0.85


def looks_like_script(content: bytes, ext: str) -> bool:
    if ext in DANGEROUS_EXTENSIONS or ext in {".html", ".htm"}:
        return True
    text = safe_text(content[:4096]).lower()
    markers = ("function ", "powershell", "<script", "wscript", "cmd.exe", "mshta")
    return any(marker in text for marker in markers)


def shannon_entropy(content: bytes) -> float:
    if not content:
        return 0.0
    counts = Counter(content)
    total = len(content)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def is_probable_tar(content: bytes) -> bool:
    return len(content) > 262 and content[257:262] in {b"ustar", b"ustar\x00"}
