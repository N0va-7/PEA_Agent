from __future__ import annotations

from pathlib import Path


class FileSystemObjectStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    async def put(self, sha256: str, content: bytes) -> str:
        path = self.root / sha256
        if not path.exists():
            path.write_bytes(content)
        return sha256

    async def get(self, object_ref: str) -> bytes | None:
        path = self.root / object_ref
        if not path.exists():
            return None
        return path.read_bytes()

    async def exists(self, object_ref: str) -> bool:
        return (self.root / object_ref).exists()
