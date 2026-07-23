"""개요와 논문 검색에 사용하는 불변 데이터 모델."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Article:
    pmid: str
    title: str
    abstract: str
    journal: str
    pub_year: int | None
    authors: str


@dataclass(frozen=True, slots=True)
class ArticleSearchCriteria:
    title_keyword: str = ""
    start_year: int | None = None
    end_year: int | None = None
    journal: str | None = None


@dataclass(frozen=True, slots=True)
class CountByLabel:
    label: str
    count: int


@dataclass(frozen=True, slots=True)
class OverviewData:
    total_articles: int
    total_journals: int
    articles_by_year: tuple[CountByLabel, ...]
    top_journals: tuple[CountByLabel, ...]


@dataclass(frozen=True, slots=True)
class CollectionSnapshot:
    """다른 팀의 수집 기능이 세션으로 전달하는 최근 결과."""

    new_count: int = 0
    skipped_count: int = 0


@dataclass(frozen=True, slots=True)
class SearchOptions:
    journals: tuple[str, ...]
    min_year: int
    max_year: int
