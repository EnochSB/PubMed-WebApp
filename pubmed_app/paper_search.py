"""요구사항 6: 저장된 논문의 필터 조회와 CSV 변환."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


PAPER_COLUMNS = ["pmid", "title", "abstract", "journal", "pub_year", "authors"]


@dataclass(frozen=True)
class PaperFilter:
    """논문 목록 화면에서 전달받는 검색 조건."""

    title: str = ""
    start_year: int | None = None
    end_year: int | None = None
    journal: str = ""


class PaperSearchRepository:
    """팀원이 수집한 SQLite 논문 데이터를 읽기 전용으로 조회한다."""

    def __init__(self, db_path: str | Path = "pubmed.db") -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        # URI의 mode=ro를 사용해 이 모듈이 수집 데이터나 스키마를 변경하지 못하게 한다.
        uri = f"file:{self.db_path.resolve().as_posix()}?mode=ro"
        return sqlite3.connect(uri, uri=True)

    def is_available(self) -> bool:
        if not self.db_path.is_file():
            return False
        try:
            with closing(self._connect()) as connection:
                with closing(
                    connection.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='papers'"
                    )
                ) as cursor:
                    row = cursor.fetchone()
            return row is not None
        except sqlite3.Error:
            return False

    def journals(self) -> list[str]:
        if not self.is_available():
            return []
        with closing(self._connect()) as connection:
            with closing(
                connection.execute(
                    "SELECT DISTINCT journal FROM papers "
                    "WHERE journal IS NOT NULL AND TRIM(journal) <> '' ORDER BY journal"
                )
            ) as cursor:
                rows = cursor.fetchall()
        return [str(row[0]) for row in rows]

    def search(self, filters: PaperFilter) -> pd.DataFrame:
        """문자열 결합 대신 바인딩 변수를 사용해 안전하게 필터링한다."""
        if not self.is_available():
            return pd.DataFrame(columns=PAPER_COLUMNS)

        conditions: list[str] = []
        parameters: list[object] = []

        if filters.title.strip():
            conditions.append("title LIKE ? ESCAPE '\\'")
            escaped = self._escape_like(filters.title.strip())
            parameters.append(f"%{escaped}%")
        if filters.start_year is not None:
            conditions.append("pub_year >= ?")
            parameters.append(filters.start_year)
        if filters.end_year is not None:
            conditions.append("pub_year <= ?")
            parameters.append(filters.end_year)
        if filters.journal.strip():
            conditions.append("journal = ?")
            parameters.append(filters.journal.strip())

        where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        query = (
            f"SELECT {', '.join(PAPER_COLUMNS)} FROM papers"
            f"{where_clause} ORDER BY pub_year DESC, pmid DESC"
        )
        # 커서를 명시적으로 닫아 Windows에서도 DB 파일 잠금이 남지 않게 한다.
        with closing(self._connect()) as connection:
            cursor = connection.execute(query, parameters)
            try:
                rows = cursor.fetchall()
            finally:
                cursor.close()
        return pd.DataFrame(rows, columns=PAPER_COLUMNS)

    @staticmethod
    def _escape_like(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class PaperCsvExporter:
    """Excel에서도 한글이 깨지지 않는 CSV 바이트를 생성한다."""

    @staticmethod
    def export(papers: pd.DataFrame) -> bytes:
        return papers.to_csv(index=False).encode("utf-8-sig")
