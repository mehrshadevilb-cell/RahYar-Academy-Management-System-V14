import asyncio
from types import SimpleNamespace

from src.services.ai_agent_knowledge_runtime import AIAgentKnowledgeRuntime


def test_publish_uses_configured_topic_for_posts_and_quizzes():
    calls = []

    class FakeBot:
        async def send_message(self, *args, **kwargs):
            calls.append(("message", args, kwargs))

        async def send_poll(self, *args, **kwargs):
            calls.append(("poll", args, kwargs))

    runtime = AIAgentKnowledgeRuntime(bot=FakeBot())
    runtime.settings.KNOWLEDGE_GROUP_TOPIC_ID = 21308

    asyncio.run(
        runtime._publish(
            [{"title": "Waves update", "text": "خبر آموزشی", "url": "https://example.com"}],
            {"question": "کدام؟", "options": ["A", "B", "C", "D"], "correct": 1, "explanation": ""},
            {-1001845120760},
        )
    )

    assert len(calls) == 2
    assert all(call[2]["message_thread_id"] == 21308 for call in calls)
