import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage, AIMessageChunk

from pubmed_app.chat_memory import SQLiteConversationStore
from pubmed_app.chatbot import (
    LITERATURE_CLASSIFIER_PROMPT,
    OPENAI_MODEL,
    ChatMessage,
    ConversationMemory,
    LiteratureQuestionClassification,
    LiteratureChatbot,
    OpenAIChatModel,
)
from pubmed_app.paper_search import PaperCsvExporter, PaperFilter, PaperSearchRepository


class FakeLanguageModel:
    """실제 OpenAI API를 호출하지 않고 고정 답변을 반환한다."""

    def __init__(self, classifications: list[bool]) -> None:
        """분류 결과와 전달된 대화·논문 문맥을 기록할 목록을 준비한다."""

        self.calls: list[tuple[list[ChatMessage], str]] = []
        self.classification_calls: list[list[ChatMessage]] = []
        self._classifications = iter(classifications)

    def classify_literature_question(
        self,
        messages: list[ChatMessage],
    ) -> bool:
        """테스트가 지정한 순서대로 논문 관련 여부를 반환한다."""

        self.classification_calls.append(list(messages))
        return next(self._classifications)

    def generate_reply(
        self,
        messages: list[ChatMessage],
        paper_context: str,
    ) -> str:
        """테스트에서 대화 메모리와 논문 문맥 전달 여부를 확인한다."""

        self.calls.append((list(messages), paper_context))
        return f"LLM 답변: {paper_context}"

    def stream_reply(
        self,
        messages: list[ChatMessage],
        paper_context: str,
    ):
        """고정 답변을 두 조각으로 나눠 스트리밍 동작을 흉내 낸다."""

        answer = self.generate_reply(messages, paper_context)
        midpoint = max(1, len(answer) // 2)
        yield answer[:midpoint]
        yield answer[midpoint:]


class FeatureFiveSixTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute(
                "CREATE TABLE articles (pmid TEXT PRIMARY KEY, title TEXT, abstract TEXT, "
                "journal TEXT, pub_year INTEGER, authors TEXT)"
            )
            connection.executemany(
                "INSERT INTO articles VALUES (?, ?, ?, ?, ?, ?)",
                [
                    ("1", "COVID-19 vaccine study", "A", "Nature", 2024, "Kim"),
                    ("2", "Cancer research", "B", "Cell", 2022, "Lee"),
                    (
                        "3",
                        '"Mourning Parts You Dreamed of Losing-But Not This Way": '
                        "The Experience of a Nonbinary Person Diagnosed With Breast Cancer.",
                        "C",
                        "Journal of Patient Experience",
                        2026,
                        "Park",
                    ),
                ],
            )
            connection.commit()
        # 통합 앱과 동일하게 3·4번 기능이 사용하는 articles 테이블을 조회한다.
        self.repository = PaperSearchRepository(self.db_path, "articles")
        self.memory_store = SQLiteConversationStore(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_filters_and_csv(self) -> None:
        papers = self.repository.search(
            PaperFilter(title="vaccine", start_year=2023, end_year=2025, journal="Nature")
        )
        self.assertEqual(["1"], papers["pmid"].tolist())
        self.assertTrue(PaperCsvExporter.export(papers).startswith(b"\xef\xbb\xbf"))

    def test_chatbot_remembers_previous_keyword(self) -> None:
        memory = ConversationMemory(self.memory_store, "chatbot-user")
        chatbot = LiteratureChatbot(
            self.repository,
            memory,
            FakeLanguageModel([True, True]),
        )
        first = chatbot.reply("COVID-19 vaccine 논문 찾아줘")
        follow_up = chatbot.reply("더 보여줘")
        self.assertIn("COVID-19 vaccine study", first)
        self.assertIn("COVID-19 vaccine study", follow_up)
        self.assertEqual(4, len(memory.messages))

    def test_paper_question_without_results_does_not_call_openai(self) -> None:
        """논문 질문의 DB 검색 결과가 없으면 OpenAI를 호출하지 않는지 확인한다."""

        language_model = FakeLanguageModel([True])
        memory = ConversationMemory(self.memory_store, "no-result-user")
        chatbot = LiteratureChatbot(self.repository, memory, language_model)

        answer = chatbot.reply("quantum entanglement 논문 찾아줘")

        self.assertIn("찾지 못했습니다", answer)
        self.assertEqual([], language_model.calls)

    def test_general_question_calls_openai_without_paper_context(self) -> None:
        """논문과 무관한 질문은 빈 논문 문맥으로 OpenAI를 호출하는지 확인한다."""

        language_model = FakeLanguageModel([False])
        memory = ConversationMemory(self.memory_store, "general-user")
        chatbot = LiteratureChatbot(self.repository, memory, language_model)

        answer = chatbot.reply("안녕하세요. 오늘 기분은 어때?")

        self.assertEqual("LLM 답변: ", answer)
        self.assertEqual(1, len(language_model.calls))
        self.assertEqual("", language_model.calls[0][1])

    def test_title_only_input_is_searched_after_semantic_classification(self) -> None:
        """논문 제목만 입력해도 의미 분류 후 DB 제목 검색을 수행한다."""

        language_model = FakeLanguageModel([True])
        memory = ConversationMemory(self.memory_store, "title-only-user")
        chatbot = LiteratureChatbot(self.repository, memory, language_model)

        answer = chatbot.reply(
            "Mourning Parts You Dreamed of Losing-But Not This Way"
        )

        self.assertIn("Mourning Parts You Dreamed of Losing-But Not This Way", answer)
        self.assertEqual(1, len(language_model.classification_calls))
        self.assertEqual(1, len(language_model.calls))

    def test_chatbot_streams_chunks_and_saves_complete_answer(self) -> None:
        """스트림 조각은 즉시 반환하고 완성된 답변만 SQLite에 저장한다."""

        language_model = FakeLanguageModel([False])
        memory = ConversationMemory(self.memory_store, "stream-user")
        chatbot = LiteratureChatbot(self.repository, memory, language_model)

        response_stream = chatbot.stream_reply("안녕하세요")
        first_chunk = next(response_stream)

        self.assertTrue(first_chunk)
        self.assertEqual(["user"], [message.role for message in memory.messages])

        answer = first_chunk + "".join(response_stream)

        self.assertEqual("LLM 답변: ", answer)
        self.assertEqual(
            ["user", "assistant"],
            [message.role for message in memory.messages],
        )
        self.assertEqual(answer, memory.messages[-1].content)

    @patch("pubmed_app.chatbot.load_dotenv")
    def test_openai_semantically_classifies_literature_context(
        self,
        load_dotenv_mock: Mock,
    ) -> None:
        """GPT 구조화 출력에 최근 문맥과 논문 제목 단독 입력을 전달한다."""

        structured_model = Mock()
        structured_model.invoke.return_value = LiteratureQuestionClassification(
            is_literature_related=True
        )
        chat_model = Mock()
        chat_model.with_structured_output.return_value = structured_model
        language_model = OpenAIChatModel(model=chat_model)
        messages = [
            ChatMessage(role="assistant", content="무엇을 도와드릴까요?"),
            ChatMessage(
                role="user",
                content="Mourning Parts You Dreamed of Losing-But Not This Way",
            ),
        ]

        result = language_model.classify_literature_question(messages)

        self.assertTrue(result)
        load_dotenv_mock.assert_called_once_with()
        chat_model.with_structured_output.assert_called_once_with(
            LiteratureQuestionClassification,
            method="json_schema",
        )
        classifier_messages = structured_model.invoke.call_args.args[0]
        self.assertEqual(LITERATURE_CLASSIFIER_PROMPT, classifier_messages[0]["content"])
        self.assertEqual(messages[-1].content, classifier_messages[-1]["content"])

    def test_sqlite_recalls_same_user_conversation_after_store_restart(self) -> None:
        """새 SQLite 저장소 객체에서도 같은 사용자의 이전 대화를 읽는지 확인한다."""

        first_request = ConversationMemory(self.memory_store, "user-1")
        first_request.add("user", "첫 번째 질문")
        first_request.last_keyword = "vaccine"

        restarted_store = SQLiteConversationStore(self.db_path)
        next_request = ConversationMemory(restarted_store, "user-1")

        self.assertEqual("첫 번째 질문", next_request.messages[0].content)
        self.assertEqual("vaccine", next_request.last_keyword)

    def test_sqlite_isolates_each_user(self) -> None:
        """같은 SQLite DB에서도 서로 다른 사용자의 대화가 섞이지 않는지 확인한다."""

        first_user = ConversationMemory(self.memory_store, "user-1")
        second_user = ConversationMemory(self.memory_store, "user-2")
        first_user.add("user", "사용자 1의 질문")
        first_user.last_keyword = "cancer"
        second_user.add("user", "사용자 2의 질문")

        self.assertEqual(["사용자 1의 질문"], [m.content for m in first_user.messages])
        self.assertEqual(["사용자 2의 질문"], [m.content for m in second_user.messages])
        self.assertEqual("", second_user.last_keyword)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-api-key"})
    @patch("pubmed_app.chatbot.create_agent")
    @patch("pubmed_app.chatbot.ChatOpenAI")
    @patch("pubmed_app.chatbot.load_dotenv")
    def test_openai_model_uses_dotenv_and_gpt_5_4_mini(
        self,
        load_dotenv_mock: Mock,
        chat_openai_mock: Mock,
        create_agent_mock: Mock,
    ) -> None:
        """OpenAI 호출 전에 .env를 읽고 정확한 모델 ID를 사용하는지 확인한다."""

        agent = Mock()
        agent.invoke.return_value = {"messages": [AIMessage(content="답변")]}
        create_agent_mock.return_value = agent
        language_model = OpenAIChatModel()

        answer = language_model.generate_reply(
            [ChatMessage(role="user", content="논문을 요약해 줘")],
            "제목: COVID-19 vaccine study",
        )

        load_dotenv_mock.assert_called_once_with()
        model_arguments = chat_openai_mock.call_args.kwargs
        self.assertEqual("gpt-5.4-mini", OPENAI_MODEL)
        self.assertEqual(OPENAI_MODEL, model_arguments["model"])
        self.assertTrue(model_arguments["use_responses_api"])
        self.assertEqual(2, len(create_agent_mock.call_args.kwargs["middleware"]))
        self.assertEqual("답변", answer)

    @patch("pubmed_app.chatbot.load_dotenv")
    @patch("pubmed_app.chatbot.create_agent")
    def test_openai_streams_only_final_answer_tokens(
        self,
        create_agent_mock: Mock,
        load_dotenv_mock: Mock,
    ) -> None:
        """의료 분류 제어값은 숨기고 최종 답변 토큰만 반환한다."""

        agent = Mock()
        agent.stream.return_value = iter(
            [
                (
                    AIMessageChunk(content="ALLOW"),
                    {"tags": ["medical_intent_classifier"]},
                ),
                (AIMessageChunk(content="스트리밍 "), {}),
                (AIMessageChunk(content="답변"), {}),
            ]
        )
        create_agent_mock.return_value = agent
        language_model = OpenAIChatModel(model=Mock())

        chunks = list(
            language_model.stream_reply(
                [ChatMessage(role="user", content="안녕하세요")],
                "",
            )
        )

        load_dotenv_mock.assert_called_once_with()
        self.assertEqual(["스트리밍 ", "답변"], chunks)
        agent.stream.assert_called_once()
        self.assertEqual(
            "messages",
            agent.stream.call_args.kwargs["stream_mode"],
        )


if __name__ == "__main__":
    unittest.main()
