from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit

from backend.agent_tools.base import AnalysisTool


RAW_URL_PATTERN = re.compile(r"https?://[^\s'\"<>]+", re.IGNORECASE)


class _HrefParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, _tag: str, attrs):
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.hrefs.append(str(value))


def _normalize_url(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        return ""
    normalized = urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path or "",
            parts.query or "",
            "",
        )
    )
    return normalized.rstrip("/") if parts.path in {"", "/"} and not parts.query else normalized


def make_url_extractor_tool() -> AnalysisTool:
    def runner(context: dict[str, object]) -> dict[str, object]:
        parsed_email = context.get("parsed_email", {}) or {}
        plain_body = str(parsed_email.get("plain_body") or parsed_email.get("body") or "")
        html_body = str(parsed_email.get("html_body") or "")

        parser = _HrefParser()
        try:
            parser.feed(html_body)
        except Exception:
            parser.hrefs = []

        raw_urls = RAW_URL_PATTERN.findall(plain_body)
        raw_urls.extend(RAW_URL_PATTERN.findall(html_body))
        raw_urls.extend(parser.hrefs)

        normalized_urls: list[str] = []
        for url in raw_urls:
            normalized = _normalize_url(url)
            if normalized:
                normalized_urls.append(normalized)

        deduped_urls = list(dict.fromkeys(normalized_urls))
        return {
            "url_extraction": {
                "raw_urls": raw_urls,
                "normalized_urls": deduped_urls,
                "extraction_source": "deterministic_parser",
            }
        }

    return AnalysisTool(
        tool_name="url_extractor",
        version="1.0.0",
        input_schema={"parsed_email": "dict"},
        output_schema={"url_extraction": "dict"},
        runner=runner,
    )
