from __future__ import annotations

import html
import re
from urllib.parse import unquote

from backend.workflow.state import EmailAnalysisState


HIGH_RISK_PATTERNS: dict[str, re.Pattern[str]] = {
    "script_tag": re.compile(r"<\s*script\b", re.IGNORECASE),
    "iframe_tag": re.compile(r"<\s*iframe\b", re.IGNORECASE),
    "svg_tag": re.compile(r"<\s*svg\b", re.IGNORECASE),
    "javascript_protocol": re.compile(r"javascript\s*:", re.IGNORECASE),
    "data_html_protocol": re.compile(r"data\s*:\s*text/html", re.IGNORECASE),
    "event_handler": re.compile(r"\bon(?:error|load|click|mouseover|focus|submit)\s*=", re.IGNORECASE),
    "cookie_access": re.compile(r"document\s*\.\s*cookie", re.IGNORECASE),
    "eval_call": re.compile(r"\beval\s*\(", re.IGNORECASE),
}

MEDIUM_RISK_PATTERNS: dict[str, re.Pattern[str]] = {
    "meta_refresh": re.compile(r"http-equiv\s*=\s*['\"]?\s*refresh", re.IGNORECASE),
    "form_action": re.compile(r"<\s*form\b[^>]*\baction\s*=", re.IGNORECASE),
    "srcdoc_attribute": re.compile(r"\bsrcdoc\s*=", re.IGNORECASE),
    "atob_call": re.compile(r"\batob\s*\(", re.IGNORECASE),
    "from_char_code": re.compile(r"fromcharcode\s*\(", re.IGNORECASE),
    "blob_download": re.compile(r"(createobjecturl|blob\s*\(|download\s*=)", re.IGNORECASE),
}


def _normalize_for_payload_scan(text: str) -> str:
    current = str(text or "")
    for _ in range(2):
        current = html.unescape(current)
        current = unquote(current)
    return current


def _match_patterns(text: str, patterns: dict[str, re.Pattern[str]]) -> list[str]:
    normalized = _normalize_for_payload_scan(text)
    hits: list[str] = []
    for name, pattern in patterns.items():
        if pattern.search(normalized):
            hits.append(name)
    return hits


def _analyze_text(text: str) -> tuple[list[str], list[str]]:
    high_hits = _match_patterns(text, HIGH_RISK_PATTERNS)
    medium_hits = _match_patterns(text, MEDIUM_RISK_PATTERNS)
    return high_hits, medium_hits


def _level_for_hits(*, high_hits: set[str], medium_hits: set[str]) -> str:
    if high_hits:
        return "high"
    if medium_hits:
        return "medium"
    return "none"


def _score_for_hits(*, high_hits: set[str], medium_hits: set[str]) -> float:
    score = min(1.0, len(high_hits) * 0.28 + len(medium_hits) * 0.12)
    if high_hits and score < 0.85:
        score = 0.85
    if not high_hits and medium_hits and score < 0.35:
        score = 0.35
    return round(score, 6)


def _summary(*, level: str, locations: list[str], hit_names: list[str]) -> str:
    if level == "none":
        return "主题与正文未命中高危 XSS/HTML payload 规则。"
    where = "、".join(locations) if locations else "邮件内容"
    hits = "、".join(hit_names[:6])
    if level == "high":
        return f"{where}命中高危 payload 规则：{hits}，需优先按脚本/XSS 风险处理。"
    return f"{where}命中可疑 payload 规则：{hits}，建议结合上下文进一步复核。"


def make_payload_guard_node():
    def payload_guard(state: EmailAnalysisState):
        subject = state.get("subject", "") or ""
        body = state.get("body", "") or ""
        html_body = state.get("html_body", "") or ""

        subject_high, subject_medium = _analyze_text(subject)
        body_high, body_medium = _analyze_text(body)
        html_high, html_medium = _analyze_text(html_body)

        high_hits = set(subject_high + body_high + html_high)
        medium_hits = set(subject_medium + body_medium + html_medium)
        medium_hits -= high_hits

        locations: list[str] = []
        if subject_high or subject_medium:
            locations.append("主题")
        if body_high or body_medium:
            locations.append("正文")
        if html_high or html_medium:
            locations.append("HTML正文")

        level = _level_for_hits(high_hits=high_hits, medium_hits=medium_hits)
        payload_analysis = {
            "level": level,
            "score": _score_for_hits(high_hits=high_hits, medium_hits=medium_hits),
            "subject_hits": sorted(set(subject_high + subject_medium)),
            "body_hits": sorted(set(body_high + body_medium)),
            "html_hits": sorted(set(html_high + html_medium)),
            "all_hits": sorted(high_hits | medium_hits),
            "locations": locations,
            "summary": _summary(level=level, locations=locations, hit_names=sorted(high_hits | medium_hits)),
        }

        return {
            "payload_analysis": payload_analysis,
            "execution_trace": state["execution_trace"] + ["payload_guard"],
        }

    return payload_guard
