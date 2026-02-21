from dataclasses import dataclass

from backend.infra.config import Settings
from backend.services.analysis_service import AnalysisService
from backend.services.job_runner import JobRunner


@dataclass
class AppContainer:
    settings: Settings
    analysis_service: AnalysisService
    job_runner: JobRunner
