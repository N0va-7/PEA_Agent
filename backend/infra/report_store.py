from datetime import datetime
from pathlib import Path


class ReportStore:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_report(self, analysis_id: str, report_content: str) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{analysis_id}_{ts}.md"
        final_path = self.output_dir / filename
        tmp_path = self.output_dir / f".{filename}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        tmp_path.replace(final_path)
        return final_path
