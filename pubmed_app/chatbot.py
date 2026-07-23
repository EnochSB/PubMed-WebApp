"""요구사항 5: 대화 이력을 기억하는 간단한 논문 탐색 챗봇."""

from __future__ import annotations

from dataclasses import dataclass, field

from pubmed_app.paper_search import PaperFilter, PaperSearchRepository


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass
class ConversationMemory:
    """Streamlit 세션 동안 사용자와 챗봇의 대화를 보관한다."""

    messages: list[ChatMessage] = field(default_factory=list)
    last_keyword: str = ""

    def add(self, role: str, content: str) -> None:
        self.messages.append(ChatMessage(role=role, content=content))

    def clear(self) -> None:
        self.messages.clear()
        self.last_keyword = ""


class LiteratureChatbot:
    """DB의 논문 제목을 찾아 답하고 직전 검색어를 대화 문맥으로 기억한다."""

    def __init__(self, repository: PaperSearchRepository, memory: ConversationMemory) -> None:
        self.repository = repository
        self.memory = memory

    def reply(self, question: str) -> str:
        clean_question = question.strip()
        self.memory.add("user", clean_question)

        if not self.repository.is_available():
            answer = "아직 조회할 논문 DB가 없습니다. 논문 수집이 완료된 뒤 다시 질문해 주세요."
        elif self._is_follow_up(clean_question) and self.memory.last_keyword:
            answer = self._search_answer(self.memory.last_keyword)
        else:
            keyword = self._extract_keyword(clean_question)
            if keyword:
                self.memory.last_keyword = keyword
                answer = self._search_answer(keyword)
            else:
                answer = (
                    "저장된 논문을 제목으로 찾아드릴 수 있습니다. "
                    "예: ‘COVID-19 vaccine 논문 찾아줘’라고 질문해 주세요."
                )

        self.memory.add("assistant", answer)
        return answer

    @staticmethod
    def _is_follow_up(question: str) -> bool:
        normalized = question.lower().replace(" ", "")
        return normalized in {"더보여줘", "다시보여줘", "그논문들", "더알려줘"}

    @staticmethod
    def _extract_keyword(question: str) -> str:
        keyword = question.strip()
        for phrase in ("논문 찾아줘", "논문 검색", "찾아줘", "검색해줘", "에 대한", "관련 논문"):
            keyword = keyword.replace(phrase, " ")
        return " ".join(keyword.split()).strip(" ?.!")

    def _search_answer(self, keyword: str) -> str:
        papers = self.repository.search(PaperFilter(title=keyword))
        if papers.empty:
            return f"‘{keyword}’이(가) 제목에 포함된 저장 논문을 찾지 못했습니다."

        lines = [f"‘{keyword}’ 검색 결과 {len(papers)}편 중 최대 5편입니다."]
        for _, paper in papers.head(5).iterrows():
            lines.append(f"- {paper['title']} ({paper['pub_year']}, {paper['journal']})")
        return "\n".join(lines)
