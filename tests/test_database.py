"""ArticleRepository의 PMID 중복 방지 테스트입니다."""

import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
