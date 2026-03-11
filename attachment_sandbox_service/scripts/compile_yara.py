from __future__ import annotations

import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from app.config import Settings
from app.rules import RuleService


def main() -> None:
    settings = Settings()
    service = RuleService(settings.rules_root, settings.compiled_rules_path)
    compiled_path = service.compile_to_disk()
    print(compiled_path)


if __name__ == "__main__":
    main()
