"""개요 화면용 집계 서비스."""

from __future__ import annotations

from pubmed_app.domain.models import OverviewData
from pubmed_app.repositories.article_repository import ArticleRepository


class OverviewService:
    def __init__(self, repository: ArticleRepository, top_journal_limit: int = 10) -> None:
        self._repository = repository
        self._top_journal_limit = max(1, top_journal_limit)

    def get_overview(self) -> OverviewData:
        return self._repository.get_overview(self._top_journal_limit)
