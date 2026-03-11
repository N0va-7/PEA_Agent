from __future__ import annotations

import json
from email.utils import parseaddr

from backend.models.tables import SystemConfig
from backend.workflow.state import EmailAnalysisState


def _extract_sender_address(sender: str) -> str:
    _, address = parseaddr(str(sender or "").strip())
    candidate = address or str(sender or "").strip()
    return candidate.strip().lower() if "@" in candidate else ""


def _extract_sender_domain(sender: str) -> str:
    sender_address = _extract_sender_address(sender)
    if not sender_address:
        return ""
    return sender_address.rsplit("@", 1)[1].strip().lower().rstrip(".")


def _load_string_list(session_factory, key: str) -> list[str]:
    if session_factory is None:
        return []
    try:
        with session_factory() as db:
            row = db.get(SystemConfig, key)
            if not row or not row.value:
                return []
            payload = json.loads(row.value)
            if not isinstance(payload, list):
                return []
            values: list[str] = []
            seen: set[str] = set()
            for item in payload:
                value = str(item or "").strip().lower().rstrip(".")
                if not value or value in seen:
                    continue
                seen.add(value)
                values.append(value)
            return values
    except Exception:
        return []


def _match_exact_sender(sender_address: str, allowlist: list[str]) -> str | None:
    candidate = str(sender_address or "").strip().lower()
    if not candidate:
        return None
    for item in allowlist:
        allowed = str(item or "").strip().lower()
        if allowed and candidate == allowed:
            return allowed
    return None


def _match_domain(sender_domain: str, allowlist: list[str]) -> str | None:
    domain = str(sender_domain or "").strip().lower().rstrip(".")
    if not domain:
        return None
    for item in allowlist:
        allowed = str(item or "").strip().lower().rstrip(".")
        if not allowed:
            continue
        if domain == allowed or domain.endswith(f".{allowed}"):
            return allowed
    return None


def make_policy_evaluation_node(session_factory=None):
    def policy_evaluation(state: EmailAnalysisState):
        sender = str(state.get("sender") or "")
        sender_address = _extract_sender_address(sender)
        sender_domain = _extract_sender_domain(sender)
        sender_whitelist = _match_exact_sender(
            sender_address,
            _load_string_list(session_factory, "sender_whitelist"),
        ) or ""
        sender_blacklist = _match_exact_sender(
            sender_address,
            _load_string_list(session_factory, "sender_blacklist"),
        ) or ""
        domain_blacklist = _match_domain(
            sender_domain,
            _load_string_list(session_factory, "domain_blacklist"),
        ) or ""

        policy_trace: list[dict] = []
        if sender_whitelist:
            policy_trace.append(
                {
                    "source": "sender_whitelist",
                    "matched_sender": sender_whitelist,
                    "sender_address": sender_address,
                }
            )
        if sender_blacklist:
            policy_trace.append(
                {
                    "source": "sender_blacklist",
                    "matched_sender": sender_blacklist,
                    "sender_address": sender_address,
                }
            )
        if domain_blacklist:
            policy_trace.append(
                {
                    "source": "domain_blacklist",
                    "matched_domain": domain_blacklist,
                    "sender_domain": sender_domain,
                }
            )

        return {
            "policy_evaluation": {
                "sender_address": sender_address,
                "sender_domain": sender_domain,
                "sender_whitelist": sender_whitelist,
                "sender_blacklist": sender_blacklist,
                "domain_blacklist": domain_blacklist,
                "policy_trace": policy_trace,
            },
            "execution_trace": state["execution_trace"] + ["policy_evaluation"],
        }

    return policy_evaluation
