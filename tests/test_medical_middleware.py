import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage

from pubmed_app.chat_memory import SQLiteConversationStore
from pubmed_app.chatbot import ConversationMemory, LiteratureChatbot
from pubmed_app.medical_middleware import (
    MEDICAL_ADVICE_KEYWORDS,
    MEDICAL_ADVICE_NOTICE,
    MEDICAL_INTENT_CLASSIFIER_PROMPT,
    MedicalAdviceBeforeAgentMiddleware,
    MedicalAdviceModelCallMiddleware,
    MedicalAdvicePolicy,
    build_medical_middleware,
)


class MedicalMiddlewareTest(unittest.TestCase):
    """요구사항 7의 의료 질문 차단 정책과 두 미들웨어를 검증한다."""

    def test_policy_has_exactly_fifteen_keywords(self) -> None:
        """정책에 선정한 주요 키워드가 정확히 15개인지 확인한다."""

        self.assertEqual(15, len(MEDICAL_ADVICE_KEYWORDS))
        self.assertEqual(15, len(set(MEDICAL_ADVICE_KEYWORDS)))

    def test_policy_blocks_required_test_question(self) -> None:
        """요구사항의 타이레놀 테스트 질문이 '먹어도'로 탐지되는지 확인한다."""

        policy = MedicalAdvicePolicy()

        self.assertEqual(
            "먹어도",
            policy.find_keyword("음주 후 타이레놀 먹어도 되나요?"),
        )

    def test_policy_normalizes_spaces_case_and_punctuation(self) -> None:
        """띄어쓰기와 영문 대소문자가 달라도 같은 키워드로 판정한다."""

        policy = MedicalAdvicePolicy()

        self.assertTrue(policy.should_block("이 약은 몇-MG 복용하나요?"))

    def test_before_agent_returns_notice_and_jumps_to_end(self) -> None:
        """Node-style 훅이 의료 질문을 고정 문구로 바꾸고 에이전트를 종료한다."""

        middleware = MedicalAdviceBeforeAgentMiddleware()

        result = middleware.before_agent(
            {"messages": [HumanMessage(content="진단해 주세요")]},
            Mock(),
        )

        self.assertIsNotNone(result)
        self.assertEqual("end", result["jump_to"])
        self.assertEqual(MEDICAL_ADVICE_NOTICE, result["messages"][0].text)

    def test_before_agent_checks_only_latest_user_prompt(self) -> None:
        """과거 의료 질문이 안전한 새 질문까지 차단하지 않는지 확인한다."""

        middleware = MedicalAdviceBeforeAgentMiddleware()

        result = middleware.before_agent(
            {
                "messages": [
                    HumanMessage(content="약 추천해 줘"),
                    AIMessage(content=MEDICAL_ADVICE_NOTICE),
                    HumanMessage(content="오늘 서울 날씨는 어때?"),
                ]
            },
            Mock(),
        )

        self.assertIsNone(result)

    def test_wrap_model_call_blocks_semantic_medical_intent(self) -> None:
        """키워드에 없는 '섭취' 표현도 의미 분류 결과에 따라 차단한다."""

        middleware = MedicalAdviceModelCallMiddleware()
        request = ModelRequest(
            model=Mock(),
            messages=[HumanMessage(content="타이레놀 섭취 할까?")],
        )
        handler = Mock(
            return_value=ModelResponse(result=[AIMessage(content="BLOCK")])
        )

        response = middleware.wrap_model_call(request, handler)

        handler.assert_called_once()
        classification_request = handler.call_args.args[0]
        self.assertEqual("타이레놀 섭취 할까?", classification_request.messages[0].text)
        self.assertEqual(
            MEDICAL_INTENT_CLASSIFIER_PROMPT,
            classification_request.system_message.text,
        )
        self.assertEqual([], classification_request.tools)
        self.assertIsInstance(response, AIMessage)
        self.assertEqual(MEDICAL_ADVICE_NOTICE, response.text)

    def test_wrap_model_call_calls_original_model_after_allow(self) -> None:
        """ALLOW로 분류된 질문은 두 번째 모델 호출에서 실제 답변을 생성한다."""

        middleware = MedicalAdviceModelCallMiddleware()
        request = ModelRequest(
            model=Mock(),
            messages=[HumanMessage(content="PubMed는 무엇인가요?")],
        )
        classification = ModelResponse(result=[AIMessage(content="ALLOW")])
        expected_answer = ModelResponse(result=[AIMessage(content="정상 답변")])
        handler = Mock(side_effect=[classification, expected_answer])

        response = middleware.wrap_model_call(request, handler)

        self.assertEqual(2, handler.call_count)
        handler.assert_called_with(request)
        self.assertIs(expected_answer, response)

    def test_wrap_model_call_fails_closed_for_invalid_classifier_output(self) -> None:
        """분류 모델이 지정 형식을 어기면 원래 질문을 모델에 보내지 않는다."""

        middleware = MedicalAdviceModelCallMiddleware()
        request = ModelRequest(
            model=Mock(),
            messages=[HumanMessage(content="이걸 사용해도 될까요?")],
        )
        handler = Mock(
            return_value=ModelResponse(result=[AIMessage(content="판단하기 어렵습니다")])
        )

        response = middleware.wrap_model_call(request, handler)

        handler.assert_called_once()
        self.assertEqual(MEDICAL_ADVICE_NOTICE, response.text)

    def test_node_style_keyword_policy_is_unchanged_for_intake_synonym(self) -> None:
        """Node-style은 기존 15개 키워드만 사용해 '섭취'를 직접 차단하지 않는다."""

        middleware = MedicalAdviceBeforeAgentMiddleware()

        result = middleware.before_agent(
            {"messages": [HumanMessage(content="타이레놀 섭취 할까?")]},
            Mock(),
        )

        self.assertIsNone(result)

    def test_langchain_agent_applies_both_middleware_layers(self) -> None:
        """실제 LangChain Agent가 의료 질문은 차단하고 안전한 질문만 모델에 보낸다."""

        fake_model = FakeMessagesListChatModel(
            responses=[
                AIMessage(content="BLOCK"),
                AIMessage(content="ALLOW"),
                AIMessage(content="모델 호출됨"),
            ]
        )
        agent = create_agent(
            model=fake_model,
            tools=[],
            middleware=build_medical_middleware(),
        )

        blocked = agent.invoke(
            {"messages": [{"role": "user", "content": "약을 처방해 주세요"}]}
        )
        semantically_blocked = agent.invoke(
            {"messages": [{"role": "user", "content": "타이레놀 섭취 할까?"}]}
        )
        safe = agent.invoke(
            {"messages": [{"role": "user", "content": "안녕하세요"}]}
        )

        self.assertEqual(MEDICAL_ADVICE_NOTICE, blocked["messages"][-1].text)
        self.assertEqual(
            MEDICAL_ADVICE_NOTICE,
            semantically_blocked["messages"][-1].text,
        )
        self.assertEqual("모델 호출됨", safe["messages"][-1].text)

    def test_chatbot_blocks_before_database_and_model_calls(self) -> None:
        """챗봇 진입점에서도 의료 질문이 DB나 모델로 전달되지 않는지 확인한다."""

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "chat.db"
            memory = ConversationMemory(SQLiteConversationStore(db_path), "medical-user")
            repository = Mock()
            language_model = Mock()
            chatbot = LiteratureChatbot(repository, memory, language_model)

            answer = chatbot.reply("음주 후 타이레놀 먹어도 되나요?")
            stored_messages = memory.messages

        self.assertEqual(MEDICAL_ADVICE_NOTICE, answer)
        repository.is_available.assert_not_called()
        language_model.generate_reply.assert_not_called()
        self.assertEqual(
            ["user", "assistant"],
            [message.role for message in stored_messages],
        )
        self.assertEqual(MEDICAL_ADVICE_NOTICE, stored_messages[-1].content)


if __name__ == "__main__":
    unittest.main()
