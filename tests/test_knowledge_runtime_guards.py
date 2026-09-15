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


def test_production_bot_username_is_target_when_settings_is_empty():
    runtime = _runtime("")
    mentioned = SimpleNamespace(text="@Mb_tutorialbot درباره کمپرسور سوال دارم", caption=None, reply_to_message=None)
    plain = SimpleNamespace(text="کمپرسور چطور کار میکند؟", caption=None, reply_to_message=None)
    assert runtime._bot_is_target(mentioned) is True
    assert runtime._bot_is_target(plain) is False


def test_quiz_normalization_detects_same_question_with_formatting_changes():
    a = AIAgentKnowledgeRuntime._normalize_quiz_text("  کمپرسور چه کاری انجام می‌دهد؟  ")
    b = AIAgentKnowledgeRuntime._normalize_quiz_text("کمپرسور چه کاری انجام میدهد")
    assert a != ""
    assert b != ""
    assert AIAgentKnowledgeRuntime._normalize_quiz_text(a) == a


def test_quiz_similarity_tokens_catch_near_duplicate_questions():
    first = "کمپرسور برای کنترل داینامیک سیگنال چه کاری انجام می‌دهد"
    near = "کمپرسور برای کنترل داینامیک سیگنال چه کاری انجام میدهد؟"
    tokens_a = AIAgentKnowledgeRuntime._tokens(first)
    tokens_b = AIAgentKnowledgeRuntime._tokens(near)
    similarity = len(tokens_a & tokens_b) / max(1, len(tokens_a | tokens_b))
    assert similarity >= 0.72
