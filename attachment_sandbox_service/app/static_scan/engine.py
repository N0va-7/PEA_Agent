from __future__ import annotations

from hashlib import sha256

from app.config import Settings
from app.models import FeatureHit
from app.rules import RuleService
from app.static_scan.demux import expand_container
from app.static_scan.models import DemuxedFile, FileProfile
from app.static_scan.parsers import parse_by_type
from app.static_scan.profiling import build_profile


class StaticScanEngine:
    def __init__(self, settings: Settings, rules: RuleService) -> None:
        self.settings = settings
        self.rules = rules

    def scan(
        self,
        *,
        content: bytes,
        filename: str,
        declared_mime: str | None,
        sample_sha256: str,
    ) -> tuple[str, list[FeatureHit], list[dict]]:
        root = DemuxedFile(
            filename=filename,
            content=content,
            declared_mime=declared_mime,
            parent_filename=None,
            depth=0,
        )
        root_profile, hits, artifacts = self._scan_file(root, sample_sha256=sample_sha256)
        return root_profile.normalized_type, dedupe_hits(hits), artifacts

    def _scan_file(self, file: DemuxedFile, *, sample_sha256: str) -> tuple[FileProfile, list[FeatureHit], list[dict]]:
        digest = sample_sha256 if file.depth == 0 else sha256(file.content).hexdigest()
        profile = build_profile(
            filename=file.filename,
            content=file.content,
            sha256=digest,
            declared_mime=file.declared_mime,
            depth=file.depth,
        )
        hits: list[FeatureHit] = []
        artifacts: list[dict] = [
            {
                "kind": "file",
                "filename": file.filename,
                "normalized_type": profile.normalized_type,
                "size_bytes": profile.size_bytes,
                "sha256": digest,
                "depth": profile.depth,
            }
        ]

        hits.extend(profile_hits(profile, self.settings))

        if self.rules.is_hash_blocked(digest):
            hits.append(
                FeatureHit(
                    reason="KNOWN_MALWARE_SIGNATURE",
                    score=100,
                    evidence=f"sha256:{digest}",
                    source="hash",
                )
            )

        hits.extend(
            self.rules.match(
                content=file.content,
                filename=file.filename,
                normalized_type=profile.normalized_type,
                declared_mime=file.declared_mime,
            )
        )

        parsed = parse_by_type(profile, file.content)
        hits.extend(parsed.hits)
        artifacts.extend(parsed.artifacts)

        children, demux_hits, child_artifacts = expand_container(
            profile=profile,
            content=file.content,
            settings=self.settings,
        )
        hits.extend(demux_hits)
        artifacts.extend(child_artifacts)

        dangerous_entries: list[str] = []
        nested_archive_count = 0
        for child in children:
            child_profile, child_hits, child_artifacts = self._scan_file(child, sample_sha256=sha256(child.content).hexdigest())
            artifacts.extend(child_artifacts)
            for hit in child_hits:
                hits.append(
                    FeatureHit(
                        reason=hit.reason,
                        score=hit.score,
                        evidence=f"{child.filename}:{hit.evidence}",
                        source=hit.source,
                        metadata=hit.metadata,
                    )
                )
            if child_profile.normalized_type in {"script", "lnk", "executable"}:
                dangerous_entries.append(f"{child.filename}:{child_profile.normalized_type}")
            if child_profile.normalized_type == "archive":
                nested_archive_count += 1
                if any(
                    hit.reason in {"SCRIPT_DOWNLOADER", "LNK_COMMAND_CHAIN", "EXECUTABLE_ATTACHMENT", "KNOWN_MALWARE_SIGNATURE"}
                    for hit in child_hits
                ):
                    dangerous_entries.append(f"{child.filename}:archive")

        if nested_archive_count > self.settings.max_archive_depth:
            hits.append(
                FeatureHit(
                    reason="ARCHIVE_RECURSION_LIMIT",
                    score=80,
                    evidence=str(nested_archive_count),
                    source="demux",
                )
            )
        if dangerous_entries:
            hits.append(
                FeatureHit(
                    reason="ARCHIVE_DANGEROUS_COMBINATION",
                    score=90,
                    evidence=", ".join(dangerous_entries[:4]),
                    source="demux",
                )
            )

        if self.rules.is_hash_allowed(digest):
            hits = [hit for hit in hits if hit.reason not in {"DECLARED_MIME_MISMATCH"}]
        return profile, hits, artifacts


def profile_hits(profile: FileProfile, settings: Settings) -> list[FeatureHit]:
    hits: list[FeatureHit] = []
    if profile.size_bytes > settings.max_file_size_bytes:
        hits.append(
            FeatureHit(
                reason="FILE_SIZE_LIMIT_EXCEEDED",
                score=80,
                evidence=str(profile.size_bytes),
                source="limits",
            )
        )
    if profile.declared_mime_group and profile.declared_mime_group != profile.normalized_type:
        hits.append(
            FeatureHit(
                reason="DECLARED_MIME_MISMATCH",
                score=15,
                evidence=f"{profile.declared_mime}->{profile.normalized_type}",
                source="profile",
            )
        )
    if profile.double_extension:
        hits.append(
            FeatureHit(
                reason="DOUBLE_EXTENSION",
                score=55,
                evidence=profile.filename,
                source="profile",
            )
        )
    return hits


def dedupe_hits(hits: list[FeatureHit]) -> list[FeatureHit]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[FeatureHit] = []
    for hit in sorted(hits, key=lambda item: item.score, reverse=True):
        key = (hit.reason, hit.evidence, hit.source)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(hit)
    return deduped
