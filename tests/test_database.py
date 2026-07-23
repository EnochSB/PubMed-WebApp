"""ArticleRepository의 PMID 중복 방지 테스트입니다."""

import tempfile
import unittest
import sqlite3
from contextlib import closing
from pathlib import Path

from database import ArticleRepository
from models import Article


class ArticleRepositoryTest(unittest.TestCase):
    """SQLite 논문 저장소의 저장 규칙을 검증합니다."""

    def test_duplicate_pmid_is_skipped(self) -> None:
        """같은 PMID를 두 번 저장할 때 두 번째 논문이 건너뛰어지는지 확인합니다."""

        with tempfile.TemporaryDirectory() as temp_dir:
            repository = ArticleRepository(Path(temp_dir) / "articles.db")
            repository.initialize()
            article = Article("123", "제목", "초록", "저널", 2025, "홍길동")

            first_result = repository.save_all([article])
            second_result = repository.save_all([article])

            self.assertEqual(first_result.inserted_count, 1)
            self.assertEqual(first_result.skipped_count, 0)
            self.assertEqual(second_result.inserted_count, 0)
            self.assertEqual(second_result.skipped_count, 1)

    def test_same_article_can_belong_to_two_users_without_copying_article(self) -> None:
        """원본 논문은 공유하되 사용자별 수집 관계가 분리되는지 확인합니다."""

        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "articles.db"
            first_user = ArticleRepository(database_path, user_id="user-a")
            second_user = ArticleRepository(database_path, user_id="user-b")
            first_user.initialize()
            second_user.initialize()
            article = Article("123", "제목", "초록", "저널", 2025, "홍길동")

            first_result = first_user.save_all([article])
            second_result = second_user.save_all([article])

            self.assertEqual(first_result.inserted_count, 1)
            self.assertEqual(second_result.inserted_count, 1)

            with closing(sqlite3.connect(database_path)) as connection:
                article_count = connection.execute(
                    "SELECT COUNT(*) FROM articles"
                ).fetchone()[0]
                ownership_count = connection.execute(
                    "SELECT COUNT(*) FROM user_articles"
                ).fetchone()[0]

            self.assertEqual(article_count, 1)
            self.assertEqual(ownership_count, 2)


if __name__ == "__main__":
    unittest.main()
