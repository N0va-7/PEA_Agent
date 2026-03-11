from __future__ import annotations

import asyncio

from app.config import Settings
from app.service import AnalysisService


async def _main() -> None:
    service = AnalysisService(Settings())
    try:
        await service.run_worker_forever()
    finally:
        await service.stop()


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
