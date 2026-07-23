"""논문 검색 조건을 정리하고 검증하는 서비스."""

from __future__ import annotations

from pubmed_app.domain.models import (
    Article,
    ArticleSearchCriteria,
    SearchOptions,
)
from pubmed_app.repositories.article_repository import ArticleRepository


class InvalidSearchCriteriaError(ValueError):
    """사용자가 입력한 검색 조건이 유효하지 않을 때 발생한다."""


class ArticleSearchService:
    def __init__(self, repository: ArticleRepository) -> None:
        self._repository = repository

    def get_options(self) -> SearchOptions:
        return self._repository.get_search_options()

    def search(self, criteria: ArticleSearchCriteria) -> tuple[Article, ...]:
        normalized = ArticleSearchCriteria(
            title_keyword=criteria.title_keyword.strip(),
            start_year=criteria.start_year,
            end_year=criteria.end_year,
            journal=criteria.journal.strip() if criteria.journal else None,
        )
        if (
            normalized.start_year is not None
            and normalized.end_year is not None
            and normalized.start_year > normalized.end_year
        ):
            raise InvalidSearchCriteriaError(
                "검색 시작 연도는 끝 연도보다 늦을 수 없습니다."
            )
        return self._repository.search(normalized)
