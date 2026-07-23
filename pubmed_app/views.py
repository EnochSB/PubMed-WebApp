"""요구사항 5·6의 Streamlit UI 컴포넌트."""

from __future__ import annotations

import hashlib
import uuid

import streamlit as st

from pubmed_app.chat_memory import ChatMemoryError, SQLiteConversationStore
from pubmed_app.chatbot import ChatbotError, ConversationMemory, LiteratureChatbot
from pubmed_app.paper_search import PaperCsvExporter, PaperFilter, PaperSearchRepository


CHAT_SESSION_USER_ID_KEY = "_chat_session_user_id"
AI_LOADING_IMAGE_HTML = """
<div style="display:flex;align-items:center;gap:0.65rem;padding:0.2rem 0;"
     role="status" aria-label="AI 답변 생성 중">
  <svg width="30" height="30" viewBox="0 0 30 30"
       xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <circle cx="15" cy="15" r="11" fill="none" stroke="#d9e2f2" stroke-width="4"/>
    <path d="M15 4a11 11 0 0 1 11 11" fill="none" stroke="#4f7cff"
          stroke-width="4" stroke-linecap="round">
      <animateTransform attributeName="transform" type="rotate"
                        from="0 15 15" to="360 15 15"
                        dur="0.8s" repeatCount="indefinite"/>
    </path>
  </svg>
  <span>답변을 생성하고 있습니다...</span>
</div>
"""


def resolve_chat_user_id() -> str:
    """로그인 사용자를 식별하고 미로그인 상태에서는 세션별 ID를 반환한다."""

    user = getattr(st, "user", None)
    if user is not None and getattr(user, "is_logged_in", False):
        # 이메일 같은 개인정보를 저장소 키에 직접 남기지 않도록 해시로 변환한다.
        identity = user.get("sub") or user.get("email")
        if identity:
            digest = hashlib.sha256(str(identity).encode("utf-8")).hexdigest()
            return f"authenticated:{digest}"

    if CHAT_SESSION_USER_ID_KEY not in st.session_state:
        st.session_state[CHAT_SESSION_USER_ID_KEY] = uuid.uuid4().hex
    return f"anonymous:{st.session_state[CHAT_SESSION_USER_ID_KEY]}"


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
    def __init__(
        self,
        repository: PaperSearchRepository,
        memory_store: SQLiteConversationStore,
    ) -> None:
        """논문 저장소와 사용자들이 공유할 대화 저장소를 연결한다."""

        self.repository = repository
        self.memory_store = memory_store

    def render(self) -> None:
        """현재 로그인 사용자의 대화만 불러와 챗봇 화면을 렌더링한다."""

        st.subheader("논문 탐색 챗봇")
        user_id = resolve_chat_user_id()
        memory = ConversationMemory(self.memory_store, user_id)
        st.caption("대화 내용은 로그인 사용자별로 SQLite에 저장됩니다.")

        if st.button("대화 내용 지우기"):
            try:
                memory.clear()
            except ChatMemoryError as error:
                st.error(str(error))
                return
            st.rerun()

        try:
            messages = memory.messages
        except ChatMemoryError as error:
            st.error(str(error))
            return

        # 대화 영역을 입력창보다 먼저 만들면 새 메시지도 항상 입력창 위에 표시된다.
        conversation_container = st.container(border=True, key="chat_panel")
        with conversation_container:
            for message in messages:
                with st.chat_message(message.role):
                    st.markdown(message.content)

        question = st.chat_input("저장된 논문에 대해 질문해 주세요")
        if question:
            chatbot = LiteratureChatbot(self.repository, memory)
            with conversation_container:
                # 모델 응답을 기다리지 않고 새 사용자 입력을 현재 실행에서 즉시 표시한다.
                with st.chat_message("user"):
                    st.markdown(question)

                with st.chat_message("assistant"):
                    loading_placeholder = st.empty()
                    loading_placeholder.markdown(
                        AI_LOADING_IMAGE_HTML,
                        unsafe_allow_html=True,
                    )

                    def visible_response_stream():
                        """첫 답변 조각이 도착할 때 로딩 이미지를 제거한다."""

                        first_chunk = True
                        try:
                            for chunk in chatbot.stream_reply(question):
                                if first_chunk:
                                    loading_placeholder.empty()
                                    first_chunk = False
                                yield chunk
                        finally:
                            # 오류나 빈 스트림이 발생해도 로딩 이미지가 남지 않게 한다.
                            loading_placeholder.empty()

                    try:
                        st.write_stream(visible_response_stream())
                    except (ChatbotError, ChatMemoryError) as error:
                        st.error(str(error))
                        return
