"""개요 집계와 논문 필터 검색의 핵심 동작을 검증한다."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from pubmed_app.domain.models import ArticleSearchCriteria
from pubmed_app.repositories.sqlite_article_repository import SQLiteArticleRepository
from pubmed_app.services.article_search_service import (
    ArticleSearchService,
    InvalidSearchCriteriaError,
)
from pubmed_app.services.overview_service import OverviewService
from pubmed_app.ui.collection_snapshot import read_collection_snapshot


class ArticleFeatureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "pubmed.db"
        self._create_fixture_database()
        repository = SQLiteArticleRepository(self.database_path)
        self.overview_service = OverviewService(repository, top_journal_limit=2)
        self.search_service = ArticleSearchService(repository)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _create_fixture_database(self) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                """
                CREATE TABLE articles (
                    pmid TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    abstract TEXT,
                    journal TEXT,
                    pub_year INTEGER,
                    authors TEXT
                )
                """
            )
            connection.executemany(
                "INSERT INTO articles VALUES (?, ?, ?, ?, ?, ?)",
                [
                    ("1", "COVID-19 vaccine study", "A", "Journal A", 2022, "Kim"),
                    ("2", "Vaccine effectiveness", "B", "Journal A", 2023, "Lee"),
                    (
                        "3",
                        "Cancer treatment",
                        "Immune marker discovered",
                        "Journal B",
                        2023,
                        "Park",
                    ),
                    ("4", "Rate 100% response", "D", "Journal C", 2024, "Choi"),
                ],
            )
            connection.commit()

    def test_overview_aggregates_articles_years_and_journals(self) -> None:
        overview = self.overview_service.get_overview()

        self.assertEqual(overview.total_articles, 4)
        self.assertEqual(overview.total_journals, 3)
        self.assertEqual(
            [(item.label, item.count) for item in overview.articles_by_year],
            [("2022", 1), ("2023", 2), ("2024", 1)],
        )
        self.assertEqual(
            [(item.label, item.count) for item in overview.top_journals],
            [("Journal A", 2), ("Journal B", 1)],
        )

    def test_search_applies_title_year_and_journal_filters(self) -> None:
        results = self.search_service.search(
            ArticleSearchCriteria(
                title_keyword="vaccine",
                start_year=2023,
                end_year=2024,
                journal="Journal A",
            )
        )

        self.assertEqual([article.pmid for article in results], ["2"])

    def test_search_treats_like_characters_as_literals(self) -> None:
        results = self.search_service.search(
            ArticleSearchCriteria(title_keyword="100%", start_year=2020, end_year=2030)
        )

        self.assertEqual([article.pmid for article in results], ["4"])

    def test_search_finds_keyword_in_abstract(self) -> None:
        results = self.search_service.search(
            ArticleSearchCriteria(
                title_keyword="Immune marker",
                start_year=2020,
                end_year=2030,
            )
        )

        self.assertEqual([article.pmid for article in results], ["3"])

    def test_search_rejects_reversed_year_range(self) -> None:
        with self.assertRaises(InvalidSearchCriteriaError):
            self.search_service.search(
                ArticleSearchCriteria(start_year=2025, end_year=2022)
            )

    def test_collection_snapshot_sanitizes_shared_session_values(self) -> None:
        snapshot = read_collection_snapshot(
            {
                "last_collection_new_count": "7",
                "last_collection_skipped_count": -2,
            }
        )

        self.assertEqual(snapshot.new_count, 7)
        self.assertEqual(snapshot.skipped_count, 0)


if __name__ == "__main__":
    unittest.main()
