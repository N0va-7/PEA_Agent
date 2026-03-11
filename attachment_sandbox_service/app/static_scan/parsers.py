from __future__ import annotations

import ipaddress
import io
import re
import zipfile
from typing import Any
from urllib.parse import urlparse, unquote

from app.models import FeatureHit
from app.static_scan.models import FileProfile, ParserOutput
from app.static_scan.profiling import safe_text

try:  # pragma: no cover - optional at import time
    import olefile
except ImportError:  # pragma: no cover
    olefile = None

try:  # pragma: no cover - optional at import time
    import pefile
except ImportError:  # pragma: no cover
    pefile = None

try:  # pragma: no cover - optional at import time
    from LnkParse3.lnk_file import LnkFile
except ImportError:  # pragma: no cover
    LnkFile = None

try:  # pragma: no cover - optional at import time
    from oletools.olevba import VBA_Parser
except ImportError:  # pragma: no cover
    VBA_Parser = None

try:  # pragma: no cover - optional at import time
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None


NETWORK_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
SUSPICIOUS_SCRIPT_MARKERS = {
    "frombase64string": ("SCRIPT_POWERSHELL_ENCODED", 85),
    " -enc ": ("SCRIPT_POWERSHELL_ENCODED", 85),
    "invoke-expression": ("SCRIPT_DOWNLOADER", 90),
    "downloadstring": ("SCRIPT_DOWNLOADER", 90),
    "invoke-webrequest": ("SCRIPT_DOWNLOADER", 90),
    "wscript.shell": ("SCRIPT_OBFUSCATED", 75),
    "createobject": ("SCRIPT_OBFUSCATED", 70),
    "mshta": ("SCRIPT_DOWNLOADER", 85),
}
SUSPICIOUS_EXECUTABLE_TERMS = (
    "powershell",
    "cmd.exe",
    "wscript",
    "shell32.dll",
    "urlmon",
    "wininet",
    "ws2_32",
    "rundll32",
    "regsvr32",
    "bitsadmin",
)
SUSPICIOUS_LNK_TERMS = (
    "powershell",
    "cmd.exe",
    "wscript",
    "mshta",
    "rundll32",
    "regsvr32",
    "cscript",
    "bitsadmin",
    "curl ",
    "wget ",
    "http://",
    "https://",
)


def parse_by_type(profile: FileProfile, content: bytes) -> ParserOutput:
    if profile.normalized_type == "office":
        return parse_office(profile, content)
    if profile.normalized_type == "pdf":
        return parse_pdf(profile, content)
    if profile.normalized_type == "script":
        return parse_script(profile, content)
    if profile.normalized_type in {"executable", "lnk"}:
        return parse_binary(profile, content)
    if profile.normalized_type == "unknown" and not profile.looks_like_text:
        return ParserOutput(
            hits=[
                FeatureHit(
                    reason="UNKNOWN_COMPOUND_FILE",
                    score=60,
                    evidence=profile.filename,
                    source="parser",
                )
            ]
        )
    return ParserOutput()


def parse_office(profile: FileProfile, content: bytes) -> ParserOutput:
    hits: list[FeatureHit] = []
    artifacts: list[dict[str, Any]] = []
    text = safe_text(content)

    if content.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = archive.namelist()
                artifacts.append(
                    {
                        "kind": "office_container",
                        "filename": profile.filename,
                        "entry_count": len(names),
                        "container": "ooxml",
                    }
                )
                if any(name.lower().endswith("vbaproject.bin") for name in names):
                    hits.append(_hit("OFFICE_VBA_MACRO", 80, "vbaProject.bin", "office"))
                if any("/embeddings/" in name.lower() for name in names):
                    hits.append(_hit("OFFICE_EMBEDDED_OLE", 70, "embeddings/", "office"))
                for name in names:
                    if not name.lower().endswith((".xml", ".rels")):
                        continue
                    try:
                        member_text = safe_text(archive.read(name)[:131072])
                    except KeyError:
                        continue
                    lowered = member_text.lower()
                    if 'targetmode="external"' in lowered or "attachedtemplate" in lowered:
                        hits.append(_hit("OFFICE_EXTERNAL_LINK", 70, name, "office"))
                    if "ddeauto" in lowered:
                        hits.append(_hit("OFFICE_DDE", 85, name, "office"))
        except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
            artifacts.append(parser_error("office-zip", exc))

    if olefile is not None:
        try:
            if olefile.isOleFile(io.BytesIO(content)):
                with olefile.OleFileIO(io.BytesIO(content)) as ole:
                    streams = ["/".join(parts) for parts in ole.listdir()]
                    artifacts.append(
                        {
                            "kind": "office_ole",
                            "filename": profile.filename,
                            "stream_count": len(streams),
                            "streams": streams[:12],
                        }
                    )
                    lowered_streams = [name.lower() for name in streams]
                    if any(name.endswith("encryptedpackage") for name in lowered_streams):
                        hits.append(_hit("OFFICE_PASSWORD_PROTECTED", 75, "EncryptedPackage", "office"))
                    if any("macros" in name or "/vba/" in name for name in lowered_streams):
                        hits.append(_hit("OFFICE_VBA_MACRO", 80, "OLE/VBA", "office"))
        except Exception as exc:  # pragma: no cover - parser-specific
            artifacts.append(parser_error("office-ole", exc))

    if VBA_Parser is not None:
        parser = None
        try:
            parser = VBA_Parser(filename=profile.filename, data=content)
            has_vba = bool(parser.detect_vba_macros())
            has_xlm = bool(parser.detect_xlm_macros())
            if has_vba or has_xlm:
                hits.append(_hit("OFFICE_VBA_MACRO", 80, "olevba", "office"))
                analysis_rows = parser.analyze_macros(show_decoded_strings=False, deobfuscate=False)
                artifacts.append(
                    {
                        "kind": "office_macro_analysis",
                        "filename": profile.filename,
                        "has_vba": has_vba,
                        "has_xlm": has_xlm,
                        "analysis_rows": len(analysis_rows),
                    }
                )
                for category, keyword, description in analysis_rows:
                    detail = f"{keyword or ''} {description or ''}".strip()
                    lowered = detail.lower()
                    if category == "AutoExec":
                        hits.append(_hit("OFFICE_AUTOEXEC_MACRO", 95, keyword or description, "office"))
                    elif category == "Suspicious":
                        if "dde" in lowered:
                            hits.append(_hit("OFFICE_DDE", 90, keyword or description, "office"))
                        elif "template injection" in lowered or "remote template" in lowered or "external" in lowered:
                            hits.append(_hit("OFFICE_EXTERNAL_LINK", 75, keyword or description, "office"))
                        else:
                            hits.append(_hit("OFFICE_VBA_MACRO", 85, keyword or description, "office"))
                    elif category == "IOC" and NETWORK_PATTERN.search(detail):
                        hits.append(_hit("OFFICE_EXTERNAL_LINK", 70, keyword or description, "office"))
        except Exception as exc:  # pragma: no cover - parser-specific
            artifacts.append(parser_error("olevba", exc))
        finally:
            if parser is not None:
                close = getattr(parser, "close", None)
                if callable(close):
                    close()

    fallback_markers = {
        "autoopen": ("OFFICE_AUTOEXEC_MACRO", 95),
        "document_open": ("OFFICE_AUTOEXEC_MACRO", 95),
        "workbook_open": ("OFFICE_AUTOEXEC_MACRO", 95),
        "ddeauto": ("OFFICE_DDE", 85),
        "targetmode=\"external\"": ("OFFICE_EXTERNAL_LINK", 70),
        "attachedtemplate": ("OFFICE_EXTERNAL_LINK", 70),
        "embeddings/": ("OFFICE_EMBEDDED_OLE", 70),
        "encryptedpackage": ("OFFICE_PASSWORD_PROTECTED", 75),
        "vbaproject.bin": ("OFFICE_VBA_MACRO", 80),
    }
    lowered_text = text.lower()
    for marker, (reason, score) in fallback_markers.items():
        if marker in lowered_text:
            hits.append(_hit(reason, score, marker, "office"))

    return ParserOutput(hits=dedupe_hits(hits), artifacts=artifacts)


def parse_pdf(profile: FileProfile, content: bytes) -> ParserOutput:
    hits: list[FeatureHit] = []
    artifacts: list[dict[str, Any]] = []
    text = safe_text(content)
    parser_succeeded = False

    if PdfReader is not None:
        try:
            reader = PdfReader(io.BytesIO(content), strict=False)
            parser_succeeded = True
            if reader.is_encrypted:
                artifacts.append(
                    {
                        "kind": "pdf_summary",
                        "filename": profile.filename,
                        "page_count": 0,
                        "encrypted": True,
                        "javascript_objects": 0,
                        "open_actions": 0,
                        "launch_actions": 0,
                        "embedded_files": 0,
                        "uri_count": 0,
                    }
                )
                hits.append(_hit("PDF_ENCRYPTED", 70, "encrypted", "pdf"))
                return ParserOutput(hits=dedupe_hits(hits), artifacts=artifacts)
            stats = {
                "javascript": 0,
                "open_action": 0,
                "launch": 0,
                "embedded_files": 0,
                "uris": set(),
            }
            _walk_pdf_object(reader.trailer, stats, set())
            page_count = 0 if reader.is_encrypted else len(reader.pages)
            artifacts.append(
                {
                    "kind": "pdf_summary",
                    "filename": profile.filename,
                    "page_count": page_count,
                    "encrypted": bool(reader.is_encrypted),
                    "javascript_objects": stats["javascript"],
                    "open_actions": stats["open_action"],
                    "launch_actions": stats["launch"],
                    "embedded_files": stats["embedded_files"],
                    "uri_count": len(stats["uris"]),
                }
            )
            if reader.is_encrypted:
                hits.append(_hit("PDF_ENCRYPTED", 70, "encrypted", "pdf"))
            if stats["javascript"]:
                hits.append(_hit("PDF_EMBEDDED_JS", 85, f"count:{stats['javascript']}", "pdf"))
            if stats["launch"]:
                hits.append(_hit("PDF_LAUNCH_ACTION", 95, f"count:{stats['launch']}", "pdf"))
            if stats["open_action"]:
                hits.append(_hit("PDF_OPEN_ACTION", 80, f"count:{stats['open_action']}", "pdf"))
            if stats["embedded_files"]:
                hits.append(_hit("PDF_EMBEDDED_FILE", 75, f"count:{stats['embedded_files']}", "pdf"))
            for uri in sorted(stats["uris"])[:3]:
                suspicious_uri = suspicious_pdf_uri(uri)
                if suspicious_uri is not None:
                    hits.append(_hit("PDF_SUSPICIOUS_URI", 40, suspicious_uri, "pdf"))
        except Exception as exc:  # pragma: no cover - parser-specific
            artifacts.append(parser_error("pypdf", exc))

    if not parser_succeeded:
        markers = {
            "/javascript": ("PDF_EMBEDDED_JS", 85),
            "/launch": ("PDF_LAUNCH_ACTION", 95),
            "/openaction": ("PDF_OPEN_ACTION", 80),
            "/embeddedfile": ("PDF_EMBEDDED_FILE", 75),
        }
        lowered = text.lower()
        for marker, (reason, score) in markers.items():
            if marker in lowered:
                hits.append(_hit(reason, score, marker, "pdf"))
        for uri in NETWORK_PATTERN.findall(text)[:3]:
            suspicious_uri = suspicious_pdf_uri(uri)
            if suspicious_uri is not None:
                hits.append(_hit("PDF_SUSPICIOUS_URI", 40, suspicious_uri, "pdf"))

    return ParserOutput(hits=dedupe_hits(hits), artifacts=artifacts)


def parse_script(profile: FileProfile, content: bytes) -> ParserOutput:
    text = safe_text(content)
    lowered = text.lower()
    hits = [
        FeatureHit(
            reason="ACTIVE_CONTENT_ATTACHMENT",
            score=60,
            evidence=profile.filename,
            source="script",
        )
    ]
    artifacts = [
        {
            "kind": "script_summary",
            "filename": profile.filename,
            "url_count": len(NETWORK_PATTERN.findall(text)),
            "looks_obfuscated": lowered.count("^") > 8 or lowered.count("`") > 8 or lowered.count("chr(") > 4,
        }
    ]
    if artifacts[0]["looks_obfuscated"]:
        hits.append(FeatureHit(reason="SCRIPT_OBFUSCATED", score=75, evidence="obfuscation", source="script"))
    for marker, (reason, score) in SUSPICIOUS_SCRIPT_MARKERS.items():
        if marker in lowered:
            hits.append(FeatureHit(reason=reason, score=score, evidence=marker, source="script"))
    for uri in NETWORK_PATTERN.findall(text)[:3]:
        hits.append(FeatureHit(reason="IOC_SUSPICIOUS_URL", score=45, evidence=uri, source="script"))
        hits.append(FeatureHit(reason="SCRIPT_DOWNLOADER", score=90, evidence=uri, source="script"))
    return ParserOutput(hits=dedupe_hits(hits), artifacts=artifacts)


def parse_binary(profile: FileProfile, content: bytes) -> ParserOutput:
    if profile.normalized_type == "lnk":
        return parse_lnk(profile, content)
    return parse_executable(profile, content)


def parse_lnk(profile: FileProfile, content: bytes) -> ParserOutput:
    hits: list[FeatureHit] = [
        FeatureHit(
            reason="ACTIVE_CONTENT_ATTACHMENT",
            score=60,
            evidence=profile.filename,
            source="lnk",
        )
    ]
    artifacts: list[dict[str, Any]] = []
    command_text = ""

    if LnkFile is not None:
        try:
            shortcut = LnkFile(indata=content)
            shortcut.process()
            payload = shortcut.get_json()
            string_data = payload.get("string_data", {})
            link_info = payload.get("link_info", {})
            command_parts = [
                str(getattr(shortcut, "lnk_command", "") or ""),
                str(string_data.get("command_line_arguments", "") or ""),
                str(string_data.get("relative_path", "") or ""),
                str(link_info.get("local_base_path", "") or ""),
                str(link_info.get("common_path_suffix", "") or ""),
            ]
            command_text = " ".join(part for part in command_parts if part).strip()
            artifacts.append(
                {
                    "kind": "lnk_summary",
                    "filename": profile.filename,
                    "command": command_text[:256],
                    "has_arguments": bool(getattr(shortcut, "has_arguments", lambda: False)()),
                    "has_link_info": bool(getattr(shortcut, "has_link_info", lambda: False)()),
                }
            )
        except Exception as exc:  # pragma: no cover - parser-specific
            artifacts.append(parser_error("lnkparse3", exc))

    lowered = f"{command_text} {safe_text(content)}".lower()
    for marker in SUSPICIOUS_LNK_TERMS:
        if marker in lowered:
            hits.append(FeatureHit(reason="LNK_COMMAND_CHAIN", score=95, evidence=marker, source="lnk"))
            break

    return ParserOutput(hits=dedupe_hits(hits), artifacts=artifacts)


def parse_executable(profile: FileProfile, content: bytes) -> ParserOutput:
    hits: list[FeatureHit] = [
        FeatureHit(
            reason="EXECUTABLE_ATTACHMENT",
            score=60,
            evidence="executable",
            source="binary",
        )
    ]
    artifacts: list[dict[str, Any]] = []
    indicators: set[str] = set()

    if pefile is not None and content.startswith(b"MZ"):
        try:
            pe = pefile.PE(data=content, fast_load=True)
            pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
            section_names: list[str] = []
            max_section_entropy = 0.0
            no_signature = True
            if hasattr(pe, "OPTIONAL_HEADER"):
                security_index = pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_SECURITY"]
                no_signature = pe.OPTIONAL_HEADER.DATA_DIRECTORY[security_index].VirtualAddress == 0
            for section in pe.sections:
                name = section.Name.rstrip(b"\x00").decode("utf-8", errors="ignore")
                section_names.append(name)
                max_section_entropy = max(max_section_entropy, float(section.get_entropy()))
            imported_names: list[str] = []
            if hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
                for entry in pe.DIRECTORY_ENTRY_IMPORT:
                    dll_name = entry.dll.decode("utf-8", errors="ignore").lower()
                    imported_names.append(dll_name)
                    for imp in entry.imports:
                        if imp.name:
                            imported_names.append(imp.name.decode("utf-8", errors="ignore").lower())
            artifacts.append(
                {
                    "kind": "pe_summary",
                    "filename": profile.filename,
                    "section_count": len(section_names),
                    "sections": section_names[:8],
                    "import_count": len(imported_names),
                    "imports": imported_names[:16],
                    "max_section_entropy": round(max_section_entropy, 3),
                    "signed": not no_signature,
                }
            )
            for marker in SUSPICIOUS_EXECUTABLE_TERMS:
                if any(marker in name for name in imported_names):
                    indicators.add(marker)
            if max_section_entropy > 7.2:
                hits.append(
                    FeatureHit(
                        reason="EXECUTABLE_HIGH_ENTROPY",
                        score=45,
                        evidence=f"section-entropy:{max_section_entropy:.2f}",
                        source="binary",
                    )
                )
        except Exception as exc:  # pragma: no cover - parser-specific
            artifacts.append(parser_error("pefile", exc))

    raw_text = safe_text(content).lower()
    for marker in SUSPICIOUS_EXECUTABLE_TERMS:
        if marker in raw_text:
            indicators.add(marker)
    for marker in sorted(indicators):
        hits.append(
            FeatureHit(
                reason="EXECUTABLE_SUSPICIOUS_IMPORT",
                score=80,
                evidence=marker,
                source="binary",
            )
        )
    if profile.entropy > 7.2:
        hits.append(
            FeatureHit(
                reason="EXECUTABLE_HIGH_ENTROPY",
                score=45,
                evidence="entropy>7.2",
                source="binary",
            )
        )
    return ParserOutput(hits=dedupe_hits(hits), artifacts=artifacts)


def _walk_pdf_object(obj: Any, stats: dict[str, Any], seen: set[int]) -> None:
    if obj is None:
        return
    try:
        resolved = obj.get_object() if hasattr(obj, "get_object") else obj
    except Exception:  # pragma: no cover - third-party object resolution
        resolved = obj

    marker = id(resolved)
    if marker in seen:
        return
    seen.add(marker)

    if isinstance(resolved, dict):
        for key, value in resolved.items():
            key_text = str(key)
            value_text = str(value)
            if key_text in {"/JS", "/JavaScript"} or value_text == "/JavaScript":
                stats["javascript"] += 1
            if key_text == "/OpenAction":
                stats["open_action"] += 1
            if key_text == "/Launch" or value_text == "/Launch":
                stats["launch"] += 1
            if key_text in {"/EmbeddedFile", "/EmbeddedFiles"} or value_text == "/EmbeddedFile":
                stats["embedded_files"] += 1
            if key_text == "/URI" and isinstance(value, str):
                stats["uris"].add(value)
            _walk_pdf_object(value, stats, seen)
        return

    if isinstance(resolved, (list, tuple)):
        for item in resolved:
            _walk_pdf_object(item, stats, seen)
        return

    if isinstance(resolved, str):
        if resolved.startswith(("http://", "https://")):
            stats["uris"].add(resolved)


def parser_error(parser: str, exc: Exception) -> dict[str, str]:
    return {
        "kind": "parser_error",
        "parser": parser,
        "message": str(exc)[:200],
    }


def suspicious_pdf_uri(uri: str) -> str | None:
    normalized = uri.rstrip(").,;]>")
    parsed = urlparse(normalized)
    host = parsed.hostname or ""
    lowered_path = unquote(f"{parsed.path}?{parsed.query}").lower()

    if "../" in lowered_path or "..\\" in lowered_path or "%2e%2e" in normalized.lower():
        return normalized

    if not host:
        return None

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None

    if address is not None and (address.is_private or address.is_loopback or address.is_reserved):
        return normalized

    return None


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


def _hit(reason: str, score: int, evidence: str, source: str) -> FeatureHit:
    return FeatureHit(reason=reason, score=score, evidence=evidence, source=source)
