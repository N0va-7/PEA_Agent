from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


Runner = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class AnalysisTool:
    tool_name: str
    version: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    runner: Runner

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        return self.runner(context)
