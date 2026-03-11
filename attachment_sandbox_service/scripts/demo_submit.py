from __future__ import annotations

import base64
import json
import sys
import time

import httpx


def submit_and_wait(base_url: str, payload: dict) -> dict:
    with httpx.Client(timeout=10, trust_env=False) as client:
        response = client.post(f"{base_url}/analysis/jobs", json=payload)
        response.raise_for_status()
        job_id = response.json()["job_id"]
        for _ in range(50):
            result = client.get(f"{base_url}/analysis/jobs/{job_id}")
            result.raise_for_status()
            body = result.json()
            if body["status"] == "completed":
                return body
            time.sleep(0.2)
    raise RuntimeError(f"job {job_id} did not complete in time")


def main() -> None:
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    benign = {
        "filename": "report.pdf",
        "source_id": "demo-client",
        "declared_mime": "application/pdf",
        "content_base64": base64.b64encode(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\n").decode(),
    }
    malicious = {
        "filename": "invoice.js",
        "source_id": "demo-client",
        "declared_mime": "application/javascript",
        "content_base64": base64.b64encode(b"Invoke-WebRequest https://evil.example/login").decode(),
    }
    outputs = {
        "benign": submit_and_wait(base_url, benign),
        "malicious": submit_and_wait(base_url, malicious),
    }
    print(json.dumps(outputs, indent=2))


if __name__ == "__main__":
    main()
