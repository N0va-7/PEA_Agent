from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RULE_NAME_RE = re.compile(r"^\s*(?:private\s+)?rule\s+([A-Za-z0-9_]+)", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ManagedRule:
    path: str
    content: str
    editable: bool
    source_kind: str
    rule_names: list[str]


class RuleAdminService:
    def __init__(self, rules_root: str | Path) -> None:
        self._rules_root = Path(rules_root)
        self._yara_root = self._rules_root / "yara"

    def list_rules(self) -> list[ManagedRule]:
        rules: list[ManagedRule] = []
        for path in sorted([*self._yara_root.rglob("*.yar"), *self._yara_root.rglob("*.yara")]):
            rules.append(self._read_rule(path))
        return rules

    def get_rule(self, rule_path: str) -> ManagedRule:
        path = self._resolve_rule_path(rule_path)
        if not path.exists():
            raise KeyError("rule not found")
        return self._read_rule(path)

    def write_rule(self, *, rule_path: str, content: str, create: bool) -> ManagedRule:
        path = self._resolve_rule_path(rule_path, must_exist=not create)
        if self._is_external(path):
            raise PermissionError("external vendored rules are read-only")
        if create and path.exists():
            raise FileExistsError("rule already exists")

        previous = path.read_text(encoding="utf-8") if path.exists() else None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return self._read_rule(path)

    def delete_rule(self, rule_path: str) -> None:
        path = self._resolve_rule_path(rule_path, must_exist=True)
        if self._is_external(path):
            raise PermissionError("external vendored rules are read-only")
        path.unlink()

    def rollback_write(self, rule_path: str, previous_content: str | None) -> None:
        path = self._resolve_rule_path(rule_path)
        if previous_content is None:
            if path.exists():
                path.unlink()
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(previous_content, encoding="utf-8")

    def snapshot(self, rule_path: str) -> str | None:
        path = self._resolve_rule_path(rule_path)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def source_kind_for(self, rule_path: str) -> str:
        path = self._resolve_rule_path(rule_path)
        return classify_source_kind(path.relative_to(self._yara_root))

    def _resolve_rule_path(self, rule_path: str, must_exist: bool = False) -> Path:
        relative = Path(rule_path)
        if relative.is_absolute():
            raise ValueError("rule path must be relative to rules/yara")
        if ".." in relative.parts:
            raise ValueError("rule path must stay within rules/yara")
        if relative.suffix not in {".yar", ".yara"}:
            raise ValueError("rule path must end with .yar or .yara")
        path = self._yara_root / relative
        if must_exist and not path.exists():
            raise KeyError("rule not found")
        return path

    def _read_rule(self, path: Path) -> ManagedRule:
        relative = path.relative_to(self._yara_root)
        content = path.read_text(encoding="utf-8")
        return ManagedRule(
            path=relative.as_posix(),
            content=content,
            editable=not self._is_external(path),
            source_kind=classify_source_kind(relative),
            rule_names=sorted(set(RULE_NAME_RE.findall(content))),
        )

    def _is_external(self, path: Path) -> bool:
        return path.relative_to(self._yara_root).parts[:1] == ("external",)


def classify_source_kind(relative_path: Path) -> str:
    parts = relative_path.parts
    if parts[:1] == ("external",):
        return "external"
    if parts[:1] == ("local",):
        return "local"
    return "builtin"


def rule_summary_payload(rule: ManagedRule) -> dict[str, Any]:
    return {
        "path": rule.path,
        "editable": rule.editable,
        "source_kind": rule.source_kind,
        "rule_names": rule.rule_names,
        "size_bytes": len(rule.content.encode("utf-8")),
    }
