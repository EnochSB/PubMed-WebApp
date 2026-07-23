"""요구사항 5·6의 Streamlit UI 컴포넌트."""

from __future__ import annotations

import streamlit as st

from pubmed_app.chatbot import ConversationMemory, LiteratureChatbot
from pubmed_app.paper_search import PaperCsvExporter, PaperFilter, PaperSearchRepository


class PaperListView:
    def __init__(self, repository: PaperSearchRepository) -> None:
        self.repository = repository

    def render(self) -> None:
        st.subheader("논문 목록")
        with st.form("paper_filter_form"):
            title = st.text_input("제목 검색어", placeholder="예: COVID-19 vaccine")
            year_col1, year_col2 = st.columns(2)
            with year_col1:
                start_year = st.number_input("시작 연도", 1900, 2100, 2020)
            with year_col2:
                end_year = st.number_input("끝 연도", 1900, 2100, 2026)
            journal_options = ["전체"] + self.repository.journals()
            journal = st.selectbox("저널", journal_options)
            submitted = st.form_submit_button("검색", type="primary")

        if submitted:
            if start_year > end_year:
                st.error("시작 연도는 끝 연도보다 클 수 없습니다.")
                return
            st.session_state.paper_search_result = self.repository.search(
                PaperFilter(
                    title=title,
                    start_year=int(start_year),
                    end_year=int(end_year),
                    journal="" if journal == "전체" else journal,
                )
            )

        papers = st.session_state.get("paper_search_result")
        if papers is None:
            st.info("검색 조건을 입력한 뒤 검색 버튼을 눌러 주세요.")
            return

        st.caption(f"검색 결과: {len(papers)}편")
        st.dataframe(papers, use_container_width=True, hide_index=True)
        st.download_button(
            "검색 결과 CSV 다운로드",
            data=PaperCsvExporter.export(papers),
            file_name="pubmed_papers.csv",
            mime="text/csv",
            disabled=papers.empty,
        )


class ChatbotView:
    def __init__(self, repository: PaperSearchRepository) -> None:
        self.repository = repository

    def render(self) -> None:
        st.subheader("논문 탐색 챗봇")
        if "chat_memory" not in st.session_state:
            st.session_state.chat_memory = ConversationMemory()
        memory: ConversationMemory = st.session_state.chat_memory

        if st.button("대화 내용 지우기"):
            memory.clear()
            st.rerun()

        for message in memory.messages:
            with st.chat_message(message.role):
                st.markdown(message.content)

        if question := st.chat_input("저장된 논문에 대해 질문해 주세요"):
            chatbot = LiteratureChatbot(self.repository, memory)
            chatbot.reply(question)
            st.rerun()

