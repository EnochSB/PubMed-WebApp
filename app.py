"""요구사항 1~6을 조립하는 Streamlit 애플리케이션 진입점."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from collection_service import ArticleCollectionService
from database import ArticleRepository, ArticleRepositoryError
from models import SearchConditions
from pubmed_client import PubMedApiError, PubMedClient
from pubmed_app.chat_memory import ChatMemoryError, SQLiteConversationStore
from pubmed_app.config import AppConfig
from pubmed_app.paper_search import PaperSearchRepository
from pubmed_app.repositories.sqlite_article_repository import SQLiteArticleRepository
from pubmed_app.services.article_search_service import ArticleSearchService
from pubmed_app.services.overview_service import OverviewService
from pubmed_app.ui.article_search_page import render_article_search_page
from pubmed_app.ui.collection_snapshot import (
    LAST_COLLECTION_NEW_COUNT_KEY,
    LAST_COLLECTION_SKIPPED_COUNT_KEY,
    read_collection_snapshot,
)
from pubmed_app.ui.overview_page import render_overview_page
from pubmed_app.views import ChatbotView


class PubMedCollectionPanel:
    """사이드바 검색 조건을 받아 PubMed 논문을 수집한다."""

    def __init__(self, collection_service: ArticleCollectionService) -> None:
        self.collection_service = collection_service

    def render(self) -> None:
        form_values = self._render_search_form()
        if form_values is None:
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

        # 개요 화면이 같은 실행의 수집 결과를 표시할 수 있도록 공유 세션에 기록한다.
        st.session_state[LAST_COLLECTION_NEW_COUNT_KEY] = result.inserted_count
        st.session_state[LAST_COLLECTION_SKIPPED_COUNT_KEY] = result.skipped_count

        if result.searched_count == 0:
            st.warning("검색 조건에 맞는 논문을 찾지 못했습니다.")
            return

        st.success(
            f"수집 완료: 신규 저장 {result.inserted_count}건, "
            f"중복 건너뜀 {result.skipped_count}건"
        )
        missing_count = result.searched_count - result.fetched_count
        if missing_count > 0:
            st.info(f"상세 정보가 없어 저장하지 못한 논문이 {missing_count}건 있습니다.")

    @staticmethod
    def _render_search_form() -> tuple[str, int, int, int] | None:
        current_year = datetime.now().year
        with st.sidebar:
            st.header("PubMed 검색 조건")
            # 폼을 사용해 수집 버튼을 누를 때만 네 조건을 한 번에 처리한다.
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
                )
                end_year = st.number_input(
                    "검색 끝 연도",
                    min_value=1800,
                    max_value=current_year,
                    value=min(2025, current_year),
                )
                max_results = st.number_input(
                    "최대 수집 논문 수",
                    min_value=1,
                    max_value=100,
                    value=100,
                )
                submitted = st.form_submit_button(
                    "논문 수집", type="primary", use_container_width=True
                )

        if not submitted:
            return None
        return keyword, int(start_year), int(end_year), int(max_results)


@st.cache_resource
def build_services(
    database_path: str,
    article_table: str,
    top_journal_limit: int,
) -> tuple[
    ArticleCollectionService,
    OverviewService,
    ArticleSearchService,
    PaperSearchRepository,
    SQLiteConversationStore,
]:
    """수집·분석·챗봇이 같은 DB와 테이블을 사용하도록 객체를 조립한다."""

    collection_repository = ArticleRepository(database_path)
    collection_repository.initialize()
    article_repository = SQLiteArticleRepository(database_path, article_table)
    chatbot_repository = PaperSearchRepository(database_path, article_table)
    chat_memory_store = SQLiteConversationStore(database_path)
    return (
        ArticleCollectionService(PubMedClient(), collection_repository),
        OverviewService(article_repository, top_journal_limit=top_journal_limit),
        ArticleSearchService(article_repository),
        chatbot_repository,
        chat_memory_store,
    )


def main() -> None:
    st.set_page_config(page_title="PubMed 논문 분석", page_icon="📚", layout="wide")
    config = AppConfig.from_environment()

    try:
        (
            collection_service,
            overview_service,
            search_service,
            chatbot_repository,
            chat_memory_store,
        ) = build_services(
            str(config.database_path),
            config.article_table,
            config.top_journal_limit,
        )
    except (ArticleRepositoryError, ChatMemoryError) as error:
        st.error(str(error))
        return

    # 먼저 수집 패널을 처리해야 갱신된 세션 통계가 같은 실행에서 개요에 반영된다.
    PubMedCollectionPanel(collection_service).render()
    collection_snapshot = read_collection_snapshot(st.session_state)

    st.title("PubMed 논문 분석 대시보드")
    st.caption("PubMed 논문을 수집하고 저장된 메타데이터를 분석·탐색합니다.")

    with st.sidebar:
        st.divider()
        st.header("최근 수집 결과")
        st.metric("신규 수집 논문", f"{collection_snapshot.new_count:,}편")
        st.metric("중복 Skip 논문", f"{collection_snapshot.skipped_count:,}편")

    overview_tab, search_tab, chatbot_tab = st.tabs(["개요", "논문 목록", "챗봇"])
    with overview_tab:
        render_overview_page(overview_service, collection_snapshot)
    with search_tab:
        render_article_search_page(search_service)
    with chatbot_tab:
        ChatbotView(chatbot_repository, chat_memory_store).render()


if __name__ == "__main__":
    main()
