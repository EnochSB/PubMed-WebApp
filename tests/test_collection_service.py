"""수집 서비스가 API 결과를 저장소에 전달하는지 테스트합니다."""

import unittest

from collection_service import ArticleCollectionService
from models import Article, SaveResult, SearchConditions


class FakePubMedClient:
    """외부 API 호출 없이 수집 서비스 흐름을 검증하는 가짜 클라이언트입니다."""

    def search_pmids(self, conditions: SearchConditions) -> list[str]:
        """테스트에 사용할 고정 PMID 두 개를 반환합니다."""

        return ["1", "2"]

    def fetch_articles(self, pmids: list[str]) -> list[Article]:
        """상세 조회 결과를 흉내 내는 논문 한 건을 반환합니다."""

        return [Article("1", "제목", "초록", "저널", 2025, "저자")]


class FakeRepository:
    """실제 SQLite를 사용하지 않고 저장 성공 결과를 반환하는 가짜 저장소입니다."""

    def save_all(self, articles: list[Article]) -> SaveResult:
        """논문 한 건이 신규 저장된 것으로 처리합니다."""

        return SaveResult(inserted_count=1, skipped_count=0)


class ArticleCollectionServiceTest(unittest.TestCase):
    """논문 수집 서비스의 단계별 처리 건수 계산을 검증합니다."""

    def test_collect_returns_each_step_count(self) -> None:
        """검색·상세 조회·저장 건수가 결과 객체에 정확히 담기는지 확인합니다."""

        service = ArticleCollectionService(FakePubMedClient(), FakeRepository())

        result = service.collect(SearchConditions("vaccine", 2022, 2025, 10))

        self.assertEqual(result.searched_count, 2)
        self.assertEqual(result.fetched_count, 1)
        self.assertEqual(result.inserted_count, 1)
        self.assertEqual(result.skipped_count, 0)


if __name__ == "__main__":
    unittest.main()
