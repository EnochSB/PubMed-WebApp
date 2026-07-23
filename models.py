"""요구사항 1·2에서 공통으로 사용하는 데이터 객체입니다."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SearchConditions:
    """사용자가 사이드바에 입력한 PubMed 검색 조건입니다."""

    keyword: str
    start_year: int
    end_year: int
    max_results: int

    def __post_init__(self) -> None:
        """검색어 공백을 정리하고 연도 범위와 최대 수집 수를 검증합니다."""

        # 앞뒤 공백을 제거해 같은 검색어가 일관된 형태로 API에 전달되게 합니다.
        object.__setattr__(self, "keyword", self.keyword.strip())

        if not self.keyword:
            raise ValueError("검색 키워드를 입력해 주세요.")
        if self.start_year > self.end_year:
            raise ValueError("검색 시작 연도는 끝 연도보다 늦을 수 없습니다.")
        if not 1 <= self.max_results <= 100:
            raise ValueError("최대 수집 논문 수는 1개에서 100개 사이여야 합니다.")


@dataclass(frozen=True, slots=True)
class Article:
    """DB에 저장할 PubMed 논문의 필수 메타데이터입니다."""

    pmid: str
    title: str
    abstract: str
    journal: str
    pub_year: int | None
    authors: str


@dataclass(frozen=True, slots=True)
class SaveResult:
    """저장소가 처리한 신규 및 중복 논문 수입니다."""

    inserted_count: int
    skipped_count: int


@dataclass(frozen=True, slots=True)
class CollectionResult:
    """한 번의 PubMed 수집 작업 결과입니다."""

    searched_count: int
    fetched_count: int
    inserted_count: int
    skipped_count: int
