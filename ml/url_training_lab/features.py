from __future__ import annotations

import math
import re
from collections import Counter
from types import SimpleNamespace
from urllib.parse import parse_qsl, urlsplit

from sklearn.base import BaseEstimator, TransformerMixin


SUSPICIOUS_TOKENS = (
    "account",
    "activity",
    "auth",
    "bank",
    "billing",
    "cmd",
    "confirm",
    "dispatch",
    "invoice",
    "login",
    "password",
    "pay",
    "recovery",
    "secure",
    "signin",
    "submit",
    "support",
    "unlock",
    "update",
    "verify",
    "wallet",
    "webscr",
)

SHORTENER_HINTS = (
    "bit.ly",
    "goo.gl",
    "is.gd",
    "ow.ly",
    "t.co",
    "tinyurl.com",
    "tad.ly",
)

IPV4_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


def _safe_urlsplit(raw_url: str):
    candidate = raw_url.strip().strip("'").strip('"').lower()
    if "://" not in candidate:
        candidate = f"http://{candidate}"
    try:
        return urlsplit(candidate)
    except ValueError:
        return SimpleNamespace(
            hostname="",
            path=candidate,
            query="",
            fragment="",
            port=None,
        )


def _shannon_entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = Counter(text)
    length = len(text)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def _has_port(parsed) -> bool:
    try:
        return parsed.port is not None
    except ValueError:
        return False


def extract_lexical_features(raw_url: str) -> dict[str, float]:
    parsed = _safe_urlsplit(raw_url)
    host = parsed.hostname or ""
    path = parsed.path or ""
    query = parsed.query or ""
    fragment = parsed.fragment or ""
    full = raw_url.strip().lower()

    token_hits = sum(token in full for token in SUSPICIOUS_TOKENS)
    digit_count = sum(ch.isdigit() for ch in full)
    alpha_count = sum(ch.isalpha() for ch in full)
    special_count = sum(not ch.isalnum() for ch in full)
    query_pairs = parse_qsl(query, keep_blank_values=True)
    host_labels = [part for part in host.split(".") if part]
    path_segments = [part for part in path.split("/") if part]

    return {
        "url_length": float(len(full)),
        "host_length": float(len(host)),
        "path_length": float(len(path)),
        "query_length": float(len(query)),
        "fragment_length": float(len(fragment)),
        "dot_count": float(full.count(".")),
        "slash_count": float(full.count("/")),
        "dash_count": float(full.count("-")),
        "underscore_count": float(full.count("_")),
        "digit_count": float(digit_count),
        "digit_ratio": float(digit_count / max(1, len(full))),
        "alpha_ratio": float(alpha_count / max(1, len(full))),
        "special_ratio": float(special_count / max(1, len(full))),
        "subdomain_depth": float(max(0, len(host_labels) - 2)),
        "path_segment_count": float(len(path_segments)),
        "query_param_count": float(len(query_pairs)),
        "token_hit_count": float(token_hits),
        "host_entropy": float(_shannon_entropy(host)),
        "path_entropy": float(_shannon_entropy(path)),
        "has_ip_host": float(bool(IPV4_RE.fullmatch(host))),
        "has_port": float(_has_port(parsed)),
        "has_at_symbol": float("@" in full),
        "has_double_slash_path": float("//" in path),
        "has_https_token_outside_scheme": float("https" in host or "https" in path),
        "has_punycode": float("xn--" in host),
        "has_shortener_hint": float(any(shortener in host for shortener in SHORTENER_HINTS)),
    }


class LexicalFeatureTransformer(BaseEstimator, TransformerMixin):
    def fit(self, x, y=None):
        return self

    def transform(self, x):
        return [extract_lexical_features(item) for item in x]
