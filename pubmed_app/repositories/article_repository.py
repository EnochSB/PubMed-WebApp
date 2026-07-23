"""서비스가 의존하는 논문 읽기 저장소 인터페이스."""

from __future__ import annotations

from typing import Protocol

from pubmed_app.domain.models import (
    Article,
    ArticleSearchCriteria,
    OverviewData,
    SearchOptions,
)


class ArticleRepository(Protocol):
    """수집/저장 책임과 분리된 조회 전용 계약."""

    def get_overview(self, top_journal_limit: int) -> OverviewData: ...

    def get_search_options(self) -> SearchOptions: ...

    def search(self, criteria: ArticleSearchCriteria) -> tuple[Article, ...]: ...
