"""애플리케이션 환경 설정."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True, slots=True)
class AppConfig:
    """환경 변수와 기본값을 한곳에서 관리한다."""

    database_path: Path
    article_table: str = "articles"
    top_journal_limit: int = 10

    @classmethod
    def from_environment(cls) -> "AppConfig":
        raw_path = Path(os.getenv("PUBMED_DB_PATH", "data/pubmed.db"))
        database_path = raw_path if raw_path.is_absolute() else PROJECT_ROOT / raw_path

        raw_limit = os.getenv("PUBMED_TOP_JOURNAL_LIMIT", "10")
        try:
            top_journal_limit = max(1, int(raw_limit))
        except ValueError:
            top_journal_limit = 10

        return cls(
            database_path=database_path.resolve(),
            article_table=os.getenv("PUBMED_ARTICLE_TABLE", "articles"),
            top_journal_limit=top_journal_limit,
        )
