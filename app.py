"""요구사항 5·6 화면만 조립하는 Streamlit 진입점."""

from pathlib import Path

import streamlit as st

from pubmed_app.paper_search import PaperSearchRepository
from pubmed_app.views import ChatbotView, PaperListView


st.set_page_config(page_title="PubMed 논문 분석", page_icon="📚", layout="wide")
st.title("PubMed 논문 분석")

# DB 경로는 팀 통합 시 환경 설정만 바꿔도 되도록 한곳에서 주입한다.
repository = PaperSearchRepository(Path("pubmed.db"))
paper_tab, chatbot_tab = st.tabs(["논문 목록", "챗봇"])

with paper_tab:
    PaperListView(repository).render()

with chatbot_tab:
    ChatbotView(repository).render()

