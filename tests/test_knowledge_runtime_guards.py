from types import SimpleNamespace

from src.services.ai_agent_knowledge_runtime import AIAgentKnowledgeRuntime


def _runtime(username="RahYarBot"):
    runtime = AIAgentKnowledgeRuntime.__new__(AIAgentKnowledgeRuntime)
    runtime.settings = SimpleNamespace(BOT_USERNAME=username)
    return runtime


def test_bot_target_requires_mention_or_reply_to_bot():
    runtime = _runtime("RahYarBot")

    plain = SimpleNamespace(text="این سوال چطور حل میشه؟", caption=None, reply_to_message=None)
    assert runtime._bot_is_target(plain) is False

    mentioned = SimpleNamespace(text="@RahYarBot این سوال چطور حل میشه؟", caption=None, reply_to_message=None)
    assert runtime._bot_is_target(mentioned) is True

    replied_to_bot = SimpleNamespace(
        text="این رو توضیح میدی؟",
        caption=None,
        reply_to_message=SimpleNamespace(from_user=SimpleNamespace(is_bot=True)),
    )
    assert runtime._bot_is_target(replied_to_bot) is True


def test_quiz_normalization_detects_same_question_with_formatting_changes():
    a = AIAgentKnowledgeRuntime._normalize_quiz_text("  کمپرسور چه کاری انجام می‌دهد؟  ")
    b = AIAgentKnowledgeRuntime._normalize_quiz_text("کمپرسور چه کاری انجام میدهد")
    assert a != ""
    assert b != ""
    assert AIAgentKnowledgeRuntime._normalize_quiz_text(a) == a
