from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yara
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "yara-python is required. Install dependencies from requirements.txt or use the Docker demo stack."
    ) from exc

from app.models import FeatureHit

EXTERNAL_RULE_OVERRIDES: dict[str, dict[str, Any]] = {
    "Contains_DDE_Protocol": {
        "reason": "OFFICE_DDE",
        "score": 95,
        "source": "yara-yara-rules",
    },
    "rtf_objdata_urlmoniker_http": {
        "reason": "OFFICE_EXPLOIT_SIGNATURE",
        "score": 95,
        "source": "yara-yara-rules",
    },
    "Maldoc_CVE_2017_11882": {
        "reason": "OFFICE_EXPLOIT_SIGNATURE",
        "score": 95,
        "source": "yara-yara-rules",
    },
    "CVE_2017_8759_Mal_HTA": {
        "reason": "KNOWN_MALWARE_SIGNATURE",
        "score": 100,
        "source": "yara-yara-rules",
    },
    "CVE_2017_8759_Mal_Doc": {
        "reason": "OFFICE_EXPLOIT_SIGNATURE",
        "score": 95,
        "source": "yara-yara-rules",
    },
    "CVE_2017_8759_SOAP_via_JS": {
        "reason": "SCRIPT_DOWNLOADER",
        "score": 90,
        "source": "yara-yara-rules",
    },
    "CVE_2017_8759_SOAP_Excel": {
        "reason": "OFFICE_EXPLOIT_SIGNATURE",
        "score": 90,
        "source": "yara-yara-rules",
    },
    "CVE_2017_8759_SOAP_txt": {
        "reason": "SCRIPT_DOWNLOADER",
        "score": 85,
        "source": "yara-yara-rules",
    },
    "CVE_2017_8759_WSDL_in_RTF": {
        "reason": "OFFICE_EXPLOIT_SIGNATURE",
        "score": 95,
        "source": "yara-yara-rules",
    },
    "Maldoc_Suspicious_OLE_target": {
        "reason": "OFFICE_EXTERNAL_LINK",
        "score": 85,
        "source": "yara-yara-rules",
    },
    "malrtf_ole2link": {
        "reason": "OFFICE_EXPLOIT_SIGNATURE",
        "score": 95,
        "source": "yara-yara-rules",
    },
}


@dataclass(frozen=True, slots=True)
class RulesetMetadata:
    version: str
    hash_blocklist: set[str]
    hash_allowlist: set[str]
    source_digest: str


@dataclass(frozen=True, slots=True)
class CompiledRuleset:
    metadata: RulesetMetadata
    compiled_rules: yara.Rules


class RuleService:
    def __init__(self, rules_root: str | Path, compiled_rules_path: str | Path) -> None:
        self._rules_root = Path(rules_root)
        self._compiled_rules_path = Path(compiled_rules_path)
        self._compiled_meta_path = self._compiled_rules_path.with_suffix(".json")
        self._rules = self._load_or_compile()

    @property
    def version(self) -> str:
        return self._rules.metadata.version

    @property
    def source_digest(self) -> str:
        return self._rules.metadata.source_digest

    def reload(self) -> None:
        self._rules = self._load_or_compile(force_recompile=True)

    def is_hash_blocked(self, sha256: str) -> bool:
        return sha256 in self._rules.metadata.hash_blocklist

    def is_hash_allowed(self, sha256: str) -> bool:
        return sha256 in self._rules.metadata.hash_allowlist

    def match(
        self,
        *,
        content: bytes,
        filename: str,
        normalized_type: str,
        declared_mime: str | None,
    ) -> list[FeatureHit]:
        externals = {
            "filename": filename,
            "normalized_type": normalized_type,
            "declared_mime": declared_mime or "",
        }
        matches = self._rules.compiled_rules.match(data=content, externals=externals)
        hits: list[FeatureHit] = []
        for match in matches:
            meta = dict(match.meta)
            reason, score, source = match_attributes(
                rule=match.rule,
                namespace=match.namespace,
                meta=meta,
            )
            evidence = first_evidence(match)
            hits.append(
                FeatureHit(
                    reason=reason,
                    score=score,
                    evidence=evidence,
                    source=source,
                    metadata={
                        "rule": match.rule,
                        "namespace": match.namespace,
                        "tags": list(match.tags),
                        "yara_meta": meta,
                    },
                )
            )
        return hits

    def compile_to_disk(self) -> Path:
        self._rules = self._compile_rules()
        self._persist_compiled_rules(self._rules)
        return self._compiled_rules_path

    def _load_or_compile(self, force_recompile: bool = False) -> CompiledRuleset:
        compiled = None if force_recompile else self._try_load_compiled_rules()
        if compiled is not None:
            return compiled
        compiled = self._compile_rules()
        self._persist_compiled_rules(compiled)
        return compiled

    def _try_load_compiled_rules(self) -> CompiledRuleset | None:
        if not self._compiled_rules_path.exists() or not self._compiled_meta_path.exists():
            return None
        metadata = self._load_compiled_metadata()
        current_digest = compute_source_digest(self._rules_root)
        if metadata.source_digest != current_digest:
            return None
        compiled = yara.load(filepath=str(self._compiled_rules_path))
        return CompiledRuleset(metadata=metadata, compiled_rules=compiled)

    def _compile_rules(self) -> CompiledRuleset:
        metadata = self._load_metadata()
        filepaths = build_filepaths(self._rules_root / "yara")
        compiled = yara.compile(
            filepaths=filepaths,
            includes=True,
            externals={
                "filename": "",
                "normalized_type": "",
                "declared_mime": "",
            },
            error_on_warning=False,
        )
        return CompiledRuleset(metadata=metadata, compiled_rules=compiled)

    def _persist_compiled_rules(self, ruleset: CompiledRuleset) -> None:
        self._compiled_rules_path.parent.mkdir(parents=True, exist_ok=True)
        ruleset.compiled_rules.save(str(self._compiled_rules_path))
        self._compiled_meta_path.write_text(
            json.dumps(
                {
                    "version": ruleset.metadata.version,
                    "hash_blocklist": sorted(ruleset.metadata.hash_blocklist),
                    "hash_allowlist": sorted(ruleset.metadata.hash_allowlist),
                    "source_digest": ruleset.metadata.source_digest,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _load_metadata(self) -> RulesetMetadata:
        manifest_path = self._rules_root / "manifest.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        return RulesetMetadata(
            version=payload["version"],
            hash_blocklist=set(payload.get("hash_blocklist", [])),
            hash_allowlist=set(payload.get("hash_allowlist", [])),
            source_digest=compute_source_digest(self._rules_root),
        )

    def _load_compiled_metadata(self) -> RulesetMetadata:
        payload = json.loads(self._compiled_meta_path.read_text(encoding="utf-8"))
        return RulesetMetadata(
            version=payload["version"],
            hash_blocklist=set(payload.get("hash_blocklist", [])),
            hash_allowlist=set(payload.get("hash_allowlist", [])),
            source_digest=payload["source_digest"],
        )


def build_filepaths(yara_root: Path) -> dict[str, str]:
    rule_files = iter_rule_files(yara_root)
    if not rule_files:
        raise RuntimeError(f"no YARA rule files found under {yara_root}")
    return {
        namespace_for_path(path.relative_to(yara_root)): str(path)
        for path in rule_files
    }


def namespace_for_path(path: Path) -> str:
    parts = list(path.with_suffix("").parts)
    return "_".join(parts)


def compute_source_digest(rules_root: Path) -> str:
    digest = hashlib.sha256()
    manifest_path = rules_root / "manifest.json"
    digest.update(manifest_path.read_bytes())
    for path in iter_rule_files(rules_root / "yara"):
        digest.update(str(path.relative_to(rules_root)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def iter_rule_files(yara_root: Path) -> list[Path]:
    return sorted(
        [
            *yara_root.rglob("*.yar"),
            *yara_root.rglob("*.yara"),
        ]
    )


def match_attributes(*, rule: str, namespace: str, meta: dict[str, Any]) -> tuple[str, int, str]:
    override = EXTERNAL_RULE_OVERRIDES.get(rule)
    if override is not None:
        return (
            str(override["reason"]),
            int(override["score"]),
            str(override["source"]),
        )

    if namespace.startswith("external_reversinglabs_") and str(meta.get("category", "")).upper() == "MALWARE":
        return ("KNOWN_MALWARE_SIGNATURE", 100, "yara-reversinglabs")

    return (
        str(meta.get("reason", "YARA_MATCH")),
        int(meta.get("score", 70)),
        str(meta.get("source", "yara")),
    )


def first_evidence(match: Any) -> str:
    if match.strings:
        string_match = match.strings[0]
        identifier = getattr(string_match, "identifier", "")
        instances = getattr(string_match, "instances", [])
        if instances:
            instance = instances[0]
            matched_data = getattr(instance, "matched_data", b"")
            if isinstance(matched_data, bytes):
                preview = matched_data[:80].decode("utf-8", errors="ignore")
            else:
                preview = str(matched_data)[:80]
            if preview:
                return f"{identifier}:{preview}"
        return str(identifier or match.rule)
    return match.rule
