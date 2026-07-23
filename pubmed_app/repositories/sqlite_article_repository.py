"""SQLite에 저장된 PubMed 논문을 조회하는 저장소."""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from pathlib import Path

from pubmed_app.domain.models import (
    Article,
    ArticleSearchCriteria,
    CountByLabel,
    OverviewData,
    SearchOptions,
)


class ArticleDataUnavailableError(RuntimeError):
    """논문 DB나 필수 테이블을 아직 사용할 수 없을 때 발생한다."""


class SQLiteArticleRepository:
    REQUIRED_COLUMNS = {"pmid", "title", "abstract", "journal", "pub_year", "authors"}

    def __init__(
        self,
        database_path: str | Path,
        table_name: str = "articles",
        *,
        user_id: str,
    ) -> None:
        self._database_path = Path(database_path).resolve()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
            raise ValueError("논문 테이블 이름에는 영문자, 숫자, 밑줄만 사용할 수 있습니다.")
        # 식별자는 매개변수 바인딩이 불가능하므로 검증한 뒤 큰따옴표로 감싼다.
        self._quoted_table = f'"{table_name}"'
        self._table_name = table_name
        self._user_id = user_id

    def _connect(self) -> sqlite3.Connection:
        if not self._database_path.is_file():
            raise ArticleDataUnavailableError(
                f"논문 DB를 찾을 수 없습니다: {self._database_path}"
            )

        try:
            connection = sqlite3.connect(
                self._database_path.as_uri() + "?mode=ro",
                uri=True,
                timeout=5,
            )
        except sqlite3.Error as error:
            raise ArticleDataUnavailableError(
                "논문 DB에 연결할 수 없습니다. 수집 기능의 DB 설정을 확인해 주세요."
            ) from error

        connection.row_factory = sqlite3.Row
        try:
            self._validate_schema(connection)
        except Exception:
            # 스키마 검증 실패 시에도 Windows에서 DB 파일 잠금이 남지 않게 한다.
            connection.close()
            raise
        return connection

    def _validate_schema(self, connection: sqlite3.Connection) -> None:
        rows = connection.execute(f"PRAGMA table_info({self._quoted_table})").fetchall()
        columns = {str(row["name"]) for row in rows}
        missing_columns = self.REQUIRED_COLUMNS - columns
        if not rows or missing_columns:
            missing_text = ", ".join(sorted(missing_columns))
            detail = f" (누락 필드: {missing_text})" if missing_text else ""
            raise ArticleDataUnavailableError(
                f"'{self._table_name}' 논문 테이블을 사용할 수 없습니다{detail}."
            )
        relation_rows = connection.execute("PRAGMA table_info(user_articles)").fetchall()
        relation_columns = {str(row["name"]) for row in relation_rows}
        if not {"user_id", "pmid"}.issubset(relation_columns):
            raise ArticleDataUnavailableError(
                "'user_articles' 사용자-논문 중계 테이블을 사용할 수 없습니다."
            )

    def get_overview(self, top_journal_limit: int) -> OverviewData:
        with closing(self._connect()) as connection:
            total_articles = int(
                connection.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM {self._quoted_table} AS article
                    INNER JOIN user_articles AS ownership
                        ON ownership.pmid = article.pmid
                    WHERE ownership.user_id = ?
                    """,
                    (self._user_id,),
                ).fetchone()[0]
            )
            total_journals = int(
                connection.execute(
                    f"""
                    SELECT COUNT(DISTINCT article.journal)
                    FROM {self._quoted_table} AS article
                    INNER JOIN user_articles AS ownership
                        ON ownership.pmid = article.pmid
                    WHERE ownership.user_id = ?
                      AND TRIM(COALESCE(article.journal, '')) <> ''
                    """,
                    (self._user_id,),
                ).fetchone()[0]
            )
            year_rows = connection.execute(
                f"""
                SELECT CAST(article.pub_year AS INTEGER) AS label,
                       COUNT(*) AS article_count
                FROM {self._quoted_table} AS article
                INNER JOIN user_articles AS ownership
                    ON ownership.pmid = article.pmid
                WHERE ownership.user_id = ?
                  AND article.pub_year IS NOT NULL
                  AND TRIM(CAST(article.pub_year AS TEXT)) <> ''
                GROUP BY CAST(article.pub_year AS INTEGER)
                ORDER BY CAST(article.pub_year AS INTEGER)
                """,
                (self._user_id,),
            ).fetchall()
            journal_rows = connection.execute(
                f"""
                SELECT article.journal AS label, COUNT(*) AS article_count
                FROM {self._quoted_table} AS article
                INNER JOIN user_articles AS ownership
                    ON ownership.pmid = article.pmid
                WHERE ownership.user_id = ?
                  AND TRIM(COALESCE(article.journal, '')) <> ''
                GROUP BY article.journal
                ORDER BY article_count DESC, article.journal COLLATE NOCASE ASC
                LIMIT ?
                """,
                (self._user_id, top_journal_limit),
            ).fetchall()

        return OverviewData(
            total_articles=total_articles,
            total_journals=total_journals,
            articles_by_year=tuple(
                CountByLabel(str(row["label"]), int(row["article_count"]))
                for row in year_rows
            ),
            top_journals=tuple(
                CountByLabel(str(row["label"]), int(row["article_count"]))
                for row in journal_rows
            ),
        )

    def get_search_options(self) -> SearchOptions:
        with closing(self._connect()) as connection:
            year_row = connection.execute(
                f"""
                SELECT MIN(CAST(article.pub_year AS INTEGER)),
                       MAX(CAST(article.pub_year AS INTEGER))
                FROM {self._quoted_table} AS article
                INNER JOIN user_articles AS ownership
                    ON ownership.pmid = article.pmid
                WHERE ownership.user_id = ?
                  AND article.pub_year IS NOT NULL
                  AND TRIM(CAST(article.pub_year AS TEXT)) <> ''
                """,
                (self._user_id,),
            ).fetchone()
            journal_rows = connection.execute(
                f"""
                SELECT DISTINCT article.journal
                FROM {self._quoted_table} AS article
                INNER JOIN user_articles AS ownership
                    ON ownership.pmid = article.pmid
                WHERE ownership.user_id = ?
                  AND TRIM(COALESCE(article.journal, '')) <> ''
                ORDER BY article.journal COLLATE NOCASE ASC
                """,
                (self._user_id,),
            ).fetchall()

        # 데이터가 비어 있어도 검색 화면의 연도 입력기는 안정적으로 표시한다.
        min_year = int(year_row[0]) if year_row[0] is not None else 1900
        max_year = int(year_row[1]) if year_row[1] is not None else 2100
        return SearchOptions(
            journals=tuple(str(row[0]) for row in journal_rows),
            min_year=min_year,
            max_year=max_year,
        )

    def search(self, criteria: ArticleSearchCriteria) -> tuple[Article, ...]:
        conditions: list[str] = ["ownership.user_id = ?"]
        parameters: list[object] = [self._user_id]

        if criteria.title_keyword:
            conditions.append("article.title LIKE ? ESCAPE '\\'")
            parameters.append(f"%{self._escape_like(criteria.title_keyword)}%")
        if criteria.start_year is not None:
            conditions.append("CAST(article.pub_year AS INTEGER) >= ?")
            parameters.append(criteria.start_year)
        if criteria.end_year is not None:
            conditions.append("CAST(article.pub_year AS INTEGER) <= ?")
            parameters.append(criteria.end_year)
        if criteria.journal:
            conditions.append("article.journal = ?")
            parameters.append(criteria.journal)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"""
            SELECT article.pmid, article.title, article.abstract, article.journal,
                   article.pub_year, article.authors
            FROM {self._quoted_table} AS article
            INNER JOIN user_articles AS ownership
                ON ownership.pmid = article.pmid
            {where_clause}
            ORDER BY CAST(article.pub_year AS INTEGER) DESC,
                     article.title COLLATE NOCASE ASC
        """

        with closing(self._connect()) as connection:
            rows = connection.execute(sql, parameters).fetchall()

        return tuple(self._row_to_article(row) for row in rows)

    @staticmethod
    def _escape_like(value: str) -> str:
        """사용자가 입력한 %, _를 와일드카드가 아닌 일반 문자로 검색한다."""

        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    @staticmethod
    def _row_to_article(row: sqlite3.Row) -> Article:
        raw_year = row["pub_year"]
        try:
            pub_year = int(raw_year) if raw_year not in (None, "") else None
        except (TypeError, ValueError):
            pub_year = None

        return Article(
            pmid=str(row["pmid"]),
            title=str(row["title"] or ""),
            abstract=str(row["abstract"] or ""),
            journal=str(row["journal"] or ""),
            pub_year=pub_year,
            authors=str(row["authors"] or ""),
        )
