from __future__ import annotations

import gzip
import io
import tarfile
import zipfile
from hashlib import sha256

from app.config import Settings
from app.models import FeatureHit
from app.static_scan.models import DemuxedFile, FileProfile
from app.static_scan.profiling import build_profile


def expand_container(
    *,
    profile: FileProfile,
    content: bytes,
    settings: Settings,
) -> tuple[list[DemuxedFile], list[FeatureHit], list[dict]]:
    if profile.normalized_type != "archive":
        return [], [], []

    hits: list[FeatureHit] = []
    artifacts: list[dict] = []
    children: list[DemuxedFile] = []
    total_uncompressed = 0

    try:
        if content.startswith(b"PK\x03\x04"):
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                infos = archive.infolist()
                if len(infos) > settings.max_archive_entries:
                    hits.append(_hit("ARCHIVE_BOMB_SUSPECTED", 95, "entry-count"))
                for info in infos[: settings.max_archive_entries]:
                    if info.flag_bits & 0x1:
                        hits.append(_hit("ARCHIVE_ENCRYPTED", 75, info.filename))
                        continue
                    total_uncompressed += info.file_size
                    if total_uncompressed > settings.max_archive_total_uncompressed or info.file_size > settings.max_archive_entry_size:
                        hits.append(_hit("ARCHIVE_BOMB_SUSPECTED", 95, info.filename))
                        continue
                    member_content = archive.read(info.filename)
                    child = _child_file(profile, info.filename, member_content)
                    children.append(child)
                    artifacts.append(artifact_for_child(child))
        elif content.startswith(b"\x1f\x8b"):
            with gzip.GzipFile(fileobj=io.BytesIO(content)) as gz:
                member_content = gz.read(settings.max_archive_entry_size + 1)
            nested_name = profile.filename[:-3] if profile.filename.endswith(".gz") else f"{profile.filename}.out"
            if len(member_content) > settings.max_archive_entry_size:
                hits.append(_hit("ARCHIVE_BOMB_SUSPECTED", 95, nested_name))
            else:
                child = _child_file(profile, nested_name, member_content)
                children.append(child)
                artifacts.append(artifact_for_child(child))
        else:
            with tarfile.open(fileobj=io.BytesIO(content)) as archive:
                infos = archive.getmembers()
                if len(infos) > settings.max_archive_entries:
                    hits.append(_hit("ARCHIVE_BOMB_SUSPECTED", 95, "entry-count"))
                for info in infos[: settings.max_archive_entries]:
                    if not info.isfile():
                        continue
                    total_uncompressed += info.size
                    if total_uncompressed > settings.max_archive_total_uncompressed or info.size > settings.max_archive_entry_size:
                        hits.append(_hit("ARCHIVE_BOMB_SUSPECTED", 95, info.name))
                        continue
                    extracted = archive.extractfile(info)
                    if extracted is None:
                        continue
                    member_content = extracted.read()
                    child = _child_file(profile, info.name, member_content)
                    children.append(child)
                    artifacts.append(artifact_for_child(child))
    except (OSError, RuntimeError, tarfile.TarError, zipfile.BadZipFile) as exc:
        hits.append(_hit("PARSER_FAILURE", 75, str(exc)))
        return [], hits, artifacts

    nested_archives = sum(
        1 for child in children if build_profile(filename=child.filename, content=child.content, sha256=sha256(child.content).hexdigest(), declared_mime=None, depth=child.depth).normalized_type == "archive"
    )
    if nested_archives > settings.max_archive_depth:
        hits.append(_hit("ARCHIVE_RECURSION_LIMIT", 80, str(nested_archives)))
    return children, hits, artifacts


def artifact_for_child(child: DemuxedFile) -> dict:
    digest = sha256(child.content).hexdigest()
    profile = build_profile(
        filename=child.filename,
        content=child.content,
        sha256=digest,
        declared_mime=child.declared_mime,
        depth=child.depth,
    )
    return {
        "kind": "archive_entry",
        "filename": child.filename,
        "normalized_type": profile.normalized_type,
        "size_bytes": len(child.content),
        "sha256": digest,
        "depth": child.depth,
    }


def _child_file(parent: FileProfile, filename: str, content: bytes) -> DemuxedFile:
    return DemuxedFile(
        filename=filename,
        content=content,
        declared_mime=None,
        parent_filename=parent.filename,
        depth=parent.depth + 1,
    )


def _hit(reason: str, score: int, evidence: str) -> FeatureHit:
    return FeatureHit(reason=reason, score=score, evidence=evidence, source="demux")
