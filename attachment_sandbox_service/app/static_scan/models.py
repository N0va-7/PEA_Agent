from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models import FeatureHit


@dataclass(frozen=True, slots=True)
class FileProfile:
    filename: str
    sha256: str
    normalized_type: str
    declared_mime: str | None
    size_bytes: int
    depth: int
    entropy: float
    looks_like_text: bool
    double_extension: bool
    declared_mime_group: str | None


@dataclass(frozen=True, slots=True)
class DemuxedFile:
    filename: str
    content: bytes
    declared_mime: str | None
    parent_filename: str | None
    depth: int


@dataclass(frozen=True, slots=True)
class ParserOutput:
    hits: list[FeatureHit] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
