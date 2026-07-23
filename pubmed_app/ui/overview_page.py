"""요구사항 3: 논문 개요 지표와 차트 화면."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from pubmed_app.domain.models import CollectionSnapshot, CountByLabel
from pubmed_app.repositories.sqlite_article_repository import ArticleDataUnavailableError
from pubmed_app.services.overview_service import OverviewService


def render_overview_page(
    service: OverviewService, collection_snapshot: CollectionSnapshot
) -> None:
    st.subheader("논문 개요")

    try:
        overview = service.get_overview()
    except ArticleDataUnavailableError as error:
        st.info(str(error))
        return

    metric_columns = st.columns(4)
    metric_columns[0].metric("전체 논문 수", f"{overview.total_articles:,}편")
    metric_columns[1].metric("최근 신규 수집", f"{collection_snapshot.new_count:,}편")
    metric_columns[2].metric(
        "최근 중복 Skip", f"{collection_snapshot.skipped_count:,}편"
    )
    metric_columns[3].metric("총 저널 수", f"{overview.total_journals:,}개")

    st.divider()
    year_column, journal_column = st.columns(2)
    with year_column:
        st.markdown("#### 연도별 논문 수")
        _render_bar_chart(overview.articles_by_year, "출판연도")
    with journal_column:
        st.markdown("#### 상위 저널")
        _render_bar_chart(overview.top_journals, "저널")


def _render_bar_chart(items: tuple[CountByLabel, ...], label_column: str) -> None:
    if not items:
        st.info("표시할 데이터가 없습니다.")
        return

    chart_data = pd.DataFrame(
        [{label_column: item.label, "논문 수": item.count} for item in items]
    )
    st.bar_chart(chart_data, x=label_column, y="논문 수", color="#2878B5")
