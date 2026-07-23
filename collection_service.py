"""PubMed 검색부터 DB 저장까지의 작업 순서를 조정하는 서비스입니다."""

from database import ArticleRepository
from models import CollectionResult, SearchConditions
from pubmed_client import PubMedClient


class ArticleCollectionService:
    """UI가 세부 API·DB 구현을 모르고 수집 작업을 실행하게 합니다."""

    def __init__(
        self,
        client: PubMedClient,
        repository: ArticleRepository,
    ) -> None:
        """PubMed 클라이언트와 논문 저장소를 서비스에 연결합니다."""

        self.client = client
        self.repository = repository

    def collect(self, conditions: SearchConditions) -> CollectionResult:
        """PMID 검색, 상세 조회, DB 저장을 순서대로 실행해 결과를 반환합니다."""

        pmids = self.client.search_pmids(conditions)
        articles = self.client.fetch_articles(pmids)
        save_result = self.repository.save_all(articles)

        return CollectionResult(
            searched_count=len(pmids),
            fetched_count=len(articles),
            inserted_count=save_result.inserted_count,
            skipped_count=save_result.skipped_count,
        )
