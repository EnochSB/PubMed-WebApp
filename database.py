"""SQLite 논문 저장소입니다.

UI와 API 코드가 SQL을 직접 다루지 않도록 저장 책임을 클래스로 분리했습니다.
"""

import sqlite3
import re
from collections.abc import Iterable
from pathlib import Path

from models import Article, SaveResult


DEFAULT_DB_PATH = Path(__file__).with_name("pubmed_articles.db")


class ArticleRepositoryError(RuntimeError):
    """논문 DB 초기화 또는 저장 실패를 UI에 전달하는 예외입니다."""


class ArticleRepository:
    """논문과 사용자별 수집 소유 관계의 중복 방지 저장을 담당합니다."""

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        user_id: str = "local-user",
        table_name: str = "articles",
    ) -> None:
        """사용할 DB, 사용자, 논문 테이블을 저장소 객체에 설정합니다."""

        self.db_path = Path(db_path)
        self.user_id = user_id
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
            raise ValueError("논문 테이블 이름에는 영문자, 숫자, 밑줄만 사용할 수 있습니다.")
        self._quoted_table = f'"{table_name}"'

    def initialize(self) -> None:
        """DB 파일과 필수 필드로 구성된 articles 테이블을 준비합니다."""

        connection: sqlite3.Connection | None = None
        try:
            # 통합 앱의 기본 경로(data/pubmed.db)가 처음 실행될 때도 생성 가능하게 한다.
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            connection = self._connect()
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._quoted_table} (
                    pmid TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    abstract TEXT NOT NULL DEFAULT '',
                    journal TEXT NOT NULL DEFAULT '',
                    pub_year INTEGER,
                    authors TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS app_users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    display_name TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # 한 논문을 여러 사용자가 수집할 수 있으므로 소유 관계를 중계 테이블로 분리한다.
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS user_articles (
                    user_id TEXT NOT NULL,
                    pmid TEXT NOT NULL,
                    collected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, pmid),
                    FOREIGN KEY (user_id) REFERENCES app_users(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (pmid) REFERENCES {self._quoted_table}(pmid) ON DELETE CASCADE
                )
                """
            )
            # 기존 단위 테스트와 로컬 저장소 사용도 외래키 제약을 만족하게 한다.
            connection.execute(
                """
                INSERT OR IGNORE INTO app_users (user_id, email, display_name)
                VALUES (?, '', '')
                """,
                (self.user_id,),
            )
            connection.commit()
        except sqlite3.Error as error:
            raise ArticleRepositoryError("논문 DB를 초기화할 수 없습니다.") from error
        finally:
            if connection is not None:
                connection.close()

    def register_user(self, email: str, display_name: str) -> None:
        """로그인한 Google 사용자의 최신 프로필을 저장한다."""

        connection: sqlite3.Connection | None = None
        try:
            connection = self._connect()
            connection.execute(
                """
                INSERT INTO app_users (user_id, email, display_name)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    email = excluded.email,
                    display_name = excluded.display_name
                """,
                (self.user_id, email, display_name),
            )
            connection.commit()
        except sqlite3.Error as error:
            raise ArticleRepositoryError("사용자 정보를 저장할 수 없습니다.") from error
        finally:
            if connection is not None:
                connection.close()

    def save_all(self, articles: Iterable[Article]) -> SaveResult:
        """논문을 저장하고 현재 사용자의 수집 목록에 연결한다."""

        inserted_count = 0
        skipped_count = 0
        connection: sqlite3.Connection | None = None

        try:
            connection = self._connect()
            connection.execute("PRAGMA foreign_keys = ON")
            for article in articles:
                # 논문 원본은 사용자 간 공유하되 각 사용자의 소유 관계는 별도로 기록한다.
                connection.execute(
                    f"""
                    INSERT OR IGNORE INTO {self._quoted_table}
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
                relation_cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO user_articles (user_id, pmid)
                    VALUES (?, ?)
                    """,
                    (self.user_id, article.pmid),
                )
                if relation_cursor.rowcount == 1:
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
