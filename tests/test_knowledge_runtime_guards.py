from datetime import datetime, timedelta
from types import SimpleNamespace

from src.services.ai_agent_knowledge_runtime import AIAgentKnowledgeRuntime
from src.database.models.knowledge import KnowledgeItem


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


def test_quiz_corpus_spreads_across_old_and_new_items():
    runtime = AIAgentKnowledgeRuntime.__new__(AIAgentKnowledgeRuntime)
    items = [
        KnowledgeItem(id=i + 1, source_type="telegram", source_key=f"k{i}", raw_text=f"note {i}", quiz_ready=True,
                      created_at=datetime(2026, 1, 1) + timedelta(days=i))
        for i in range(100)
    ]
    class FakeDB:
        def scalars(self, statement):
            class Result:
                def all(self_inner):
                    return items
            return Result()
    selected = runtime._quiz_corpus(FakeDB())
    assert selected[0].id == 1
    assert selected[-1].id == 100
    assert len(selected) == 36
