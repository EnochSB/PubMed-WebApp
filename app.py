"""요구사항 3(개요)과 4(논문 검색)를 제공하는 Streamlit 진입점."""

from __future__ import annotations

import streamlit as st

from pubmed_app.config import AppConfig
from pubmed_app.repositories.sqlite_article_repository import SQLiteArticleRepository
from pubmed_app.services.article_search_service import ArticleSearchService
from pubmed_app.services.overview_service import OverviewService
from pubmed_app.ui.article_search_page import render_article_search_page
from pubmed_app.ui.collection_snapshot import read_collection_snapshot
from pubmed_app.ui.overview_page import render_overview_page


@st.cache_resource
def build_services(
    database_path: str, article_table: str, top_journal_limit: int
) -> tuple[OverviewService, ArticleSearchService]:
    """DB 연결 객체를 재사용하되 화면에서는 구체적인 저장 방식을 알지 못하게 한다."""

    repository = SQLiteArticleRepository(database_path, article_table)
    return (
        OverviewService(repository, top_journal_limit=top_journal_limit),
        ArticleSearchService(repository),
    )


def main() -> None:
    st.set_page_config(
        page_title="PubMed 논문 분석",
        page_icon="📚",
        layout="wide",
    )

    config = AppConfig.from_environment()
    overview_service, search_service = build_services(
        str(config.database_path),
        config.article_table,
        config.top_journal_limit,
    )
    collection_snapshot = read_collection_snapshot(st.session_state)

    st.title("PubMed 논문 분석 대시보드")
    st.caption("저장된 PubMed 메타데이터의 현황을 확인하고 논문을 검색합니다.")

    # 수집 기능은 다른 팀원의 담당이므로 여기서는 공유 세션 값을 읽어 표시만 한다.
    with st.sidebar:
        st.header("최근 수집 결과")
        st.metric("신규 수집 논문", f"{collection_snapshot.new_count:,}편")
        st.metric("중복 Skip 논문", f"{collection_snapshot.skipped_count:,}편")
        st.caption("수집 기능이 전달한 가장 최근 실행 결과입니다.")

    overview_tab, search_tab = st.tabs(["개요", "논문 목록"])
    with overview_tab:
        render_overview_page(overview_service, collection_snapshot)
    with search_tab:
        render_article_search_page(search_service)


if __name__ == "__main__":
    main()
