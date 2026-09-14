from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.database.models.support_request import SupportRequest


def support_ticket_keyboard(request: SupportRequest) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 پاسخ", callback_data=f"support_reply_{request.id}"
                ),
                InlineKeyboardButton(
                    text="✅ بستن", callback_data=f"support_close_{request.id}"
                ),
            ],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_support")],
        ]
    )


def support_open_list_keyboard(requests: list[SupportRequest]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in requests:
        preview = item.message.replace("\n", " ")[:40]
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"#{item.id} — {preview}",
                    callback_data=f"support_view_{item.id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
