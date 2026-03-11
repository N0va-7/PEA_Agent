from __future__ import annotations

from dataclasses import dataclass

from app.models import AnalysisResult, FeatureHit, Verdict


@dataclass(frozen=True, slots=True)
class SignalProfile:
    suspicious_weight: int = 0
    malicious_weight: int = 0


SIGNAL_PROFILES = {
    "ACTIVE_CONTENT_ATTACHMENT": SignalProfile(suspicious_weight=20),
    "ARCHIVE_BOMB_SUSPECTED": SignalProfile(malicious_weight=90),
    "ARCHIVE_DANGEROUS_COMBINATION": SignalProfile(malicious_weight=95),
    "ARCHIVE_ENCRYPTED": SignalProfile(suspicious_weight=55),
    "ARCHIVE_RECURSION_LIMIT": SignalProfile(suspicious_weight=40),
    "DECLARED_MIME_MISMATCH": SignalProfile(suspicious_weight=10),
    "DOUBLE_EXTENSION": SignalProfile(suspicious_weight=35),
    "EXECUTABLE_ATTACHMENT": SignalProfile(suspicious_weight=40),
    "EXECUTABLE_HIGH_ENTROPY": SignalProfile(suspicious_weight=25),
    "EXECUTABLE_SUSPICIOUS_IMPORT": SignalProfile(suspicious_weight=35, malicious_weight=20),
    "FILE_SIZE_LIMIT_EXCEEDED": SignalProfile(suspicious_weight=35),
    "IOC_SUSPICIOUS_URL": SignalProfile(suspicious_weight=25, malicious_weight=15),
    "KNOWN_MALWARE_SIGNATURE": SignalProfile(malicious_weight=100),
    "LNK_COMMAND_CHAIN": SignalProfile(malicious_weight=95),
    "OFFICE_AUTOEXEC_MACRO": SignalProfile(suspicious_weight=35, malicious_weight=45),
    "OFFICE_DDE": SignalProfile(malicious_weight=85),
    "OFFICE_EMBEDDED_OLE": SignalProfile(suspicious_weight=30),
    "OFFICE_EXPLOIT_SIGNATURE": SignalProfile(malicious_weight=95),
    "OFFICE_EXTERNAL_LINK": SignalProfile(suspicious_weight=25),
    "OFFICE_PASSWORD_PROTECTED": SignalProfile(suspicious_weight=50),
    "OFFICE_VBA_MACRO": SignalProfile(suspicious_weight=45),
    "PARSER_FAILURE": SignalProfile(suspicious_weight=50),
    "PDF_EMBEDDED_FILE": SignalProfile(suspicious_weight=30, malicious_weight=20),
    "PDF_EMBEDDED_JS": SignalProfile(suspicious_weight=45, malicious_weight=25),
    "PDF_ENCRYPTED": SignalProfile(suspicious_weight=50),
    "PDF_LAUNCH_ACTION": SignalProfile(malicious_weight=95),
    "PDF_OPEN_ACTION": SignalProfile(suspicious_weight=30, malicious_weight=10),
    "PDF_SUSPICIOUS_URI": SignalProfile(suspicious_weight=30),
    "SCRIPT_DOWNLOADER": SignalProfile(malicious_weight=70),
    "SCRIPT_OBFUSCATED": SignalProfile(suspicious_weight=20),
    "SCRIPT_POWERSHELL_ENCODED": SignalProfile(malicious_weight=80),
    "UNKNOWN_COMPOUND_FILE": SignalProfile(suspicious_weight=35),
}


def decide(
    *,
    normalized_type: str,
    feature_hits: list[FeatureHit],
    artifacts: list[dict],
    rule_version: str,
) -> AnalysisResult:
    reasons = unique_reasons(feature_hits)
    strongest = strongest_hits(feature_hits)
    reason_set = set(reasons)

    if "KNOWN_MALWARE_SIGNATURE" in reason_set:
        verdict = Verdict.BLOCK
        risk_score = 100
    else:
        suspicious_score, malicious_score = aggregate_scores(strongest)
        suspicious_score, malicious_score = apply_combo_adjustments(
            normalized_type=normalized_type,
            reason_set=reason_set,
            suspicious_score=suspicious_score,
            malicious_score=malicious_score,
        )
        risk_score = min(100, max(suspicious_score, malicious_score))
        verdict = classify_verdict(
            normalized_type=normalized_type,
            reason_set=reason_set,
            suspicious_score=suspicious_score,
            malicious_score=malicious_score,
        )

    return AnalysisResult(
        verdict=verdict,
        risk_score=risk_score,
        reasons=reasons,
        normalized_type=normalized_type,
        artifacts=artifacts,
        feature_hits=feature_hits,
        rule_version=rule_version,
    )


def aggregate_scores(strongest: dict[str, FeatureHit]) -> tuple[int, int]:
    suspicious_score = 0
    malicious_score = 0
    for reason, hit in strongest.items():
        profile = SIGNAL_PROFILES.get(reason, SignalProfile())
        suspicious_score += weighted_signal(hit.score, profile.suspicious_weight)
        malicious_score += weighted_signal(hit.score, profile.malicious_weight)
    return min(100, suspicious_score), min(100, malicious_score)


def apply_combo_adjustments(
    *,
    normalized_type: str,
    reason_set: set[str],
    suspicious_score: int,
    malicious_score: int,
) -> tuple[int, int]:
    if "SCRIPT_DOWNLOADER" in reason_set and "IOC_SUSPICIOUS_URL" in reason_set:
        malicious_score = max(malicious_score, 95)
    if "OFFICE_AUTOEXEC_MACRO" in reason_set and (
        "OFFICE_VBA_MACRO" in reason_set or "OFFICE_DDE" in reason_set
    ):
        malicious_score = max(malicious_score, 95)
    if "PDF_EMBEDDED_JS" in reason_set and (
        "PDF_OPEN_ACTION" in reason_set or "PDF_EMBEDDED_FILE" in reason_set or "PDF_LAUNCH_ACTION" in reason_set
    ):
        malicious_score = max(malicious_score, 90)
    if "ARCHIVE_DANGEROUS_COMBINATION" in reason_set:
        malicious_score = max(malicious_score, 95)
    if "ARCHIVE_ENCRYPTED" in reason_set and normalized_type == "archive":
        suspicious_score = max(suspicious_score, 60)
    return min(100, suspicious_score), min(100, malicious_score)


def classify_verdict(
    *,
    normalized_type: str,
    reason_set: set[str],
    suspicious_score: int,
    malicious_score: int,
) -> Verdict:
    hard_block_reasons = {
        "ARCHIVE_BOMB_SUSPECTED",
        "ARCHIVE_DANGEROUS_COMBINATION",
        "KNOWN_MALWARE_SIGNATURE",
        "LNK_COMMAND_CHAIN",
        "OFFICE_DDE",
        "OFFICE_EXPLOIT_SIGNATURE",
        "PDF_LAUNCH_ACTION",
        "SCRIPT_POWERSHELL_ENCODED",
    }
    if reason_set & hard_block_reasons:
        return Verdict.BLOCK
    if malicious_score >= 90:
        return Verdict.BLOCK
    hard_quarantine_reasons = {
        "ARCHIVE_ENCRYPTED",
        "EXECUTABLE_ATTACHMENT",
        "OFFICE_EMBEDDED_OLE",
        "OFFICE_EXTERNAL_LINK",
        "OFFICE_PASSWORD_PROTECTED",
        "OFFICE_VBA_MACRO",
        "PARSER_FAILURE",
        "PDF_EMBEDDED_FILE",
        "PDF_EMBEDDED_JS",
        "PDF_ENCRYPTED",
        "PDF_OPEN_ACTION",
        "PDF_SUSPICIOUS_URI",
        "UNKNOWN_COMPOUND_FILE",
    }
    if reason_set & hard_quarantine_reasons:
        return Verdict.QUARANTINE
    if suspicious_score >= 30 or malicious_score >= 45:
        return Verdict.QUARANTINE
    if normalized_type in {"script", "executable", "lnk", "unknown"}:
        return Verdict.QUARANTINE
    return Verdict.ALLOW


def weighted_signal(hit_score: int, profile_weight: int) -> int:
    if profile_weight <= 0:
        return 0
    return round((hit_score * profile_weight) / 100)


def strongest_hits(feature_hits: list[FeatureHit]) -> dict[str, FeatureHit]:
    strongest: dict[str, FeatureHit] = {}
    for hit in sorted(feature_hits, key=lambda item: item.score, reverse=True):
        current = strongest.get(hit.reason)
        if current is None or hit.score > current.score:
            strongest[hit.reason] = hit
    return strongest


def unique_reasons(feature_hits: list[FeatureHit]) -> list[str]:
    reasons: list[str] = []
    seen: set[str] = set()
    for hit in sorted(feature_hits, key=lambda item: item.score, reverse=True):
        if hit.reason in seen:
            continue
        seen.add(hit.reason)
        reasons.append(hit.reason)
    return reasons
