"""요구사항 4: 제목·연도·저널 필터 기반 논문 목록 화면."""

from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st

from pubmed_app.domain.models import Article, ArticleSearchCriteria
from pubmed_app.paper_search import PaperCsvExporter
from pubmed_app.repositories.sqlite_article_repository import ArticleDataUnavailableError
from pubmed_app.services.article_search_service import (
    ArticleSearchService,
    InvalidSearchCriteriaError,
)


SEARCH_RESULTS_KEY = "requirement_4_search_results"
SEARCH_EXECUTED_KEY = "requirement_4_search_executed"


def render_article_search_page(service: ArticleSearchService) -> None:
    st.subheader("논문 검색")
    st.caption("제목 검색어, 출판연도 범위, 저널 조건을 함께 적용할 수 있습니다.")

    try:
        options = service.get_options()
    except ArticleDataUnavailableError as error:
        st.info(str(error))
        return

    with st.form("article_search_form"):
        title_keyword = st.text_input(
            "제목 검색어",
            placeholder="예: COVID-19 vaccine",
        )
        start_column, end_column, journal_column = st.columns(3)
        with start_column:
            start_year = st.number_input(
                "검색 시작 연도",
                min_value=0,
                max_value=9999,
                value=options.min_year,
                step=1,
            )
        with end_column:
            end_year = st.number_input(
                "검색 끝 연도",
                min_value=0,
                max_value=9999,
                value=options.max_year,
                step=1,
            )
        with journal_column:
            selected_journal = st.selectbox("저널", ("전체", *options.journals))

        submitted = st.form_submit_button(
            "검색",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        criteria = ArticleSearchCriteria(
            title_keyword=title_keyword,
            start_year=int(start_year),
            end_year=int(end_year),
            journal=None if selected_journal == "전체" else selected_journal,
        )
        try:
            st.session_state[SEARCH_RESULTS_KEY] = service.search(criteria)
            st.session_state[SEARCH_EXECUTED_KEY] = True
        except InvalidSearchCriteriaError as error:
            st.error(str(error))
            return
        except ArticleDataUnavailableError as error:
            st.error(str(error))
            return

    if not st.session_state.get(SEARCH_EXECUTED_KEY, False):
        st.info("검색 조건을 입력한 뒤 검색 버튼을 눌러 주세요.")
        return

    results = st.session_state.get(SEARCH_RESULTS_KEY, ())
    st.markdown(f"#### 검색 결과: {len(results):,}편")
    if not results:
        st.warning("검색 조건에 해당하는 논문이 없습니다.")
        return

    _render_results(results)


def _render_results(results: tuple[Article, ...]) -> None:
    # CSV는 DB 필드명을 유지하고, 화면에서만 읽기 쉬운 한국어 열 이름을 사용한다.
    dataframe = pd.DataFrame(asdict(article) for article in results)
    display_dataframe = dataframe.rename(
        columns={
            "pmid": "PMID",
            "title": "제목",
            "abstract": "초록",
            "journal": "저널",
            "pub_year": "출판연도",
            "authors": "저자",
        }
    )
    st.dataframe(
        display_dataframe,
        hide_index=True,
        use_container_width=True,
        column_config={
            "PMID": st.column_config.TextColumn(width="small"),
            "제목": st.column_config.TextColumn(width="large"),
            "초록": st.column_config.TextColumn(width="large"),
            "저널": st.column_config.TextColumn(width="medium"),
            "출판연도": st.column_config.NumberColumn(format="%d"),
            "저자": st.column_config.TextColumn(width="large"),
        },
    )
    st.download_button(
        "검색 결과 CSV 다운로드",
        data=PaperCsvExporter.export(dataframe),
        file_name="pubmed_papers.csv",
        mime="text/csv",
        use_container_width=True,
    )
