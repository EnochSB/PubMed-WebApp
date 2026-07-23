"""요구사항 1·2 전용 Streamlit 애플리케이션 진입점입니다."""

from datetime import datetime

import streamlit as st

from collection_service import ArticleCollectionService
from database import ArticleRepository, ArticleRepositoryError
from models import SearchConditions
from pubmed_client import PubMedApiError, PubMedClient


class PubMedCollectionApp:
    """검색 조건 UI를 그리고 논문 수집 서비스를 호출합니다."""

    def __init__(self, collection_service: ArticleCollectionService) -> None:
        """UI에서 사용할 논문 수집 서비스를 외부에서 주입받습니다."""

        self.collection_service = collection_service

    def run(self) -> None:
        """메인 안내 화면을 표시하고 제출된 검색 조건으로 수집을 실행합니다."""

        st.title("PubMed 논문 메타데이터 수집")
        st.caption("검색 조건에 맞는 논문을 PubMed에서 수집해 DB에 저장합니다.")

        form_values = self._render_search_form()
        if form_values is None:
            st.info("왼쪽 사이드바에서 조건을 입력하고 ‘논문 수집’ 버튼을 눌러 주세요.")
            return

        keyword, start_year, end_year, max_results = form_values
        try:
            conditions = SearchConditions(
                keyword=keyword,
                start_year=start_year,
                end_year=end_year,
                max_results=max_results,
            )
            with st.spinner("PubMed에서 논문을 수집하고 있습니다..."):
                result = self.collection_service.collect(conditions)
        except (ValueError, PubMedApiError, ArticleRepositoryError) as error:
            st.error(str(error))
            return

        if result.searched_count == 0:
            st.warning("검색 조건에 맞는 논문을 찾지 못했습니다.")
            return

        # 대시보드 통계가 아니라 이번 수집 요청의 저장 결과만 안내합니다.
        st.success(
            f"수집을 완료했습니다. 신규 저장 {result.inserted_count}건, "
            f"중복 건너뜀 {result.skipped_count}건"
        )
        missing_count = result.searched_count - result.fetched_count
        if missing_count > 0:
            st.info(f"상세 정보가 없어 저장하지 못한 논문이 {missing_count}건 있습니다.")

    @staticmethod
    def _render_search_form() -> tuple[str, int, int, int] | None:
        """요구사항 1의 네 가지 검색 위젯과 수집 버튼을 그립니다."""

        current_year = datetime.now().year
        with st.sidebar:
            st.header("PubMed 검색 조건")
            # form을 사용해 수집 버튼을 누를 때만 입력값을 한 번에 처리합니다.
            with st.form("pubmed_search_form"):
                keyword = st.text_input(
                    "검색 키워드",
                    value="COVID-19 vaccine",
                    placeholder="예: COVID-19 vaccine",
                )
                start_year = st.number_input(
                    "검색 시작 연도",
                    min_value=1800,
                    max_value=current_year,
                    value=min(2022, current_year),
                    step=1,
                )
                end_year = st.number_input(
                    "검색 끝 연도",
                    min_value=1800,
                    max_value=current_year,
                    value=min(2025, current_year),
                    step=1,
                )
                max_results = st.number_input(
                    "최대 수집 논문 수",
                    min_value=1,
                    max_value=100,
                    value=100,
                    step=1,
                )
                submitted = st.form_submit_button(
                    "논문 수집",
                    type="primary",
                    use_container_width=True,
                )

        if not submitted:
            return None
        return keyword, int(start_year), int(end_year), int(max_results)


@st.cache_resource
def create_collection_service() -> ArticleCollectionService:
    """앱 재실행마다 API 세션과 저장소 객체를 새로 만들지 않도록 구성합니다."""

    repository = ArticleRepository()
    repository.initialize()
    return ArticleCollectionService(PubMedClient(), repository)


def main() -> None:
    """Streamlit 페이지를 설정하고 애플리케이션 실행을 시작합니다."""

    st.set_page_config(page_title="PubMed 논문 수집", page_icon="🔎", layout="wide")
    try:
        collection_service = create_collection_service()
    except ArticleRepositoryError as error:
        st.error(str(error))
        return
    PubMedCollectionApp(collection_service).run()


if __name__ == "__main__":
    main()
