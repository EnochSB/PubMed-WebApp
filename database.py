"""SQLite 논문 저장소입니다.

UI와 API 코드가 SQL을 직접 다루지 않도록 저장 책임을 클래스로 분리했습니다.
"""

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from models import Article, SaveResult


DEFAULT_DB_PATH = Path(__file__).with_name("pubmed_articles.db")


class ArticleRepositoryError(RuntimeError):
    """논문 DB 초기화 또는 저장 실패를 UI에 전달하는 예외입니다."""


class ArticleRepository:
    """논문 테이블 생성과 PMID 중복 방지 저장을 담당합니다."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        """사용할 SQLite 파일 경로를 저장소 객체에 설정합니다."""

        self.db_path = Path(db_path)

    def initialize(self) -> None:
        """DB 파일과 필수 필드로 구성된 articles 테이블을 준비합니다."""

        connection: sqlite3.Connection | None = None
        try:
            connection = self._connect()
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS articles (
                    pmid TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    abstract TEXT NOT NULL DEFAULT '',
                    journal TEXT NOT NULL DEFAULT '',
                    pub_year INTEGER,
                    authors TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.commit()
        except sqlite3.Error as error:
            raise ArticleRepositoryError("논문 DB를 초기화할 수 없습니다.") from error
        finally:
            if connection is not None:
                connection.close()

    def save_all(self, articles: Iterable[Article]) -> SaveResult:
        """논문을 저장하고 PMID가 이미 존재하면 해당 행을 건너뜁니다."""

        inserted_count = 0
        skipped_count = 0
        connection: sqlite3.Connection | None = None

        try:
            connection = self._connect()
            for article in articles:
                # pmid가 기본키이므로 INSERT OR IGNORE로 원자적인 중복 방지가 가능합니다.
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO articles
                        (pmid, title, abstract, journal, pub_year, authors)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        article.pmid,
                        article.title,
                        article.abstract,
                        article.journal,
                        article.pub_year,
                        article.authors,
                    ),
                )
                if cursor.rowcount == 1:
                    inserted_count += 1
                else:
                    skipped_count += 1

            connection.commit()
        except sqlite3.Error as error:
            # 일부 데이터만 저장되는 일을 막기 위해 오류가 나면 전체 작업을 취소합니다.
            if connection is not None:
                connection.rollback()
            raise ArticleRepositoryError("수집한 논문을 DB에 저장할 수 없습니다.") from error
        finally:
            if connection is not None:
                connection.close()

        return SaveResult(inserted_count, skipped_count)

    def _connect(self) -> sqlite3.Connection:
        """저장소 내부에서만 SQLite 연결 생성 방법을 관리합니다."""

        return sqlite3.connect(self.db_path)
