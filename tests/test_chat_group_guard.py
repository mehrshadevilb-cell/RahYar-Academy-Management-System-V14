import pytest

from aiogram.types import MessageEntity, MessageEntityType

from src.bot.handlers.chat_assistant import _group_message_targets_bot


class _User:
    def __init__(self, user_id):
        self.id = user_id


class _Bot:
    id = 12345

    async def get_me(self):
        return _UserName()


class _UserName:
    username = "RahYarBot"


class _Chat:
    def __init__(self, chat_type):
        self.type = chat_type


class _Message:
    def __init__(self, *, chat_type="group", text="", entities=None, reply_user_id=None):
        self.chat = _Chat(chat_type)
        self.bot = _Bot()
        self.text = text
        self.entities = entities or []
        self.reply_to_message = None
        if reply_user_id is not None:
            self.reply_to_message = type("Reply", (), {"from_user": _User(reply_user_id)})()


@pytest.mark.asyncio
async def test_group_message_is_ignored_without_direct_address():
    message = _Message(text="بچه‌ها کسی می‌دونه این پلاگین چیه؟")
    assert await _group_message_targets_bot(message) is False


@pytest.mark.asyncio
async def test_group_message_answers_when_replied_to_bot():
    message = _Message(text="ادامه بده", reply_user_id=12345)
    assert await _group_message_targets_bot(message) is True


@pytest.mark.asyncio
async def test_group_message_answers_on_username_mention():
    message = _Message(
        text="سلام @RahYarBot اینو توضیح بده",
        entities=[MessageEntity(type=MessageEntityType.MENTION, offset=5, length=9)],
    )
    assert await _group_message_targets_bot(message) is True


@pytest.mark.asyncio
async def test_private_message_is_not_restricted():
    message = _Message(chat_type="private", text="سلام")
    assert await _group_message_targets_bot(message) is True
