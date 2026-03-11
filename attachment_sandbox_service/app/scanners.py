from __future__ import annotations

import asyncio
import struct

from app.models import FeatureHit


class ClamAVScanner:
    def __init__(self, *, enabled: bool, host: str, port: int, timeout_seconds: float) -> None:
        self.enabled = enabled
        self.host = host
        self.port = port
        self.timeout_seconds = timeout_seconds

    async def scan(self, content: bytes) -> list[FeatureHit]:
        if not self.enabled:
            return []
        try:
            return await asyncio.wait_for(self._scan_stream(content), timeout=self.timeout_seconds)
        except Exception as exc:
            return [
                FeatureHit(
                    reason="AV_SCANNER_UNAVAILABLE",
                    score=70,
                    evidence=str(exc),
                    source="clamav",
                )
            ]

    async def _scan_stream(self, content: bytes) -> list[FeatureHit]:
        reader, writer = await asyncio.open_connection(self.host, self.port)
        writer.write(b"zINSTREAM\0")
        chunk_size = 8192
        for offset in range(0, len(content), chunk_size):
            chunk = content[offset : offset + chunk_size]
            writer.write(struct.pack(">I", len(chunk)))
            writer.write(chunk)
        writer.write(struct.pack(">I", 0))
        await writer.drain()
        raw = await reader.read(4096)
        writer.close()
        await writer.wait_closed()
        response = raw.decode("utf-8", errors="ignore")
        if "FOUND" not in response:
            return []
        signature = response.split("FOUND", 1)[0].split(":")[-1].strip()
        return [
            FeatureHit(
                reason="KNOWN_MALWARE_SIGNATURE",
                score=100,
                evidence=signature or "clamav",
                source="clamav",
            )
        ]
