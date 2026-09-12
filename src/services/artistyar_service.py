import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.orm import Session

from src.database.models.course import Course
from src.database.models.invite_link import TelegramInviteLink
from src.database.repositories.invite_link_repository import InviteLinkRepository


logger = logging.getLogger("artistyar")

RETRY_DELAYS_SECONDS = [1, 3]


class ArtistYarService:
    """
    Generates one-time Telegram invite links for ArtistYar-type products
    (Record / Edit / Files channels, or whichever channels are configured).

    The bot must already be an admin with "invite users via link"
    permission in every configured channel, or link generation will fail
    for that channel.

    Safe to call again for the same user/product: channels that already
    have a link are skipped, so this function doubles as its own retry -
    calling it again only attempts the channels that previously failed.
    """

    def __init__(self):
        self.repository = InviteLinkRepository()

    async def deliver_channels(
        self,
        bot: Bot,
        db: Session,
        user_id: int,
        product: Course,
    ) -> list[dict]:
        """
        Returns a list of per-channel results:
        {"channel_name": str, "invite_link": str | None, "error": str | None}
        """

        results = []

        enabled_channels = [
            channel
            for channel in product.telegram_channels
            if channel.enabled
        ]

        for channel in enabled_channels:

            existing = self.repository.get_by_user_and_channel(
                db, user_id, channel.id
            )

            if existing:

                results.append({
                    "channel_name": channel.name,
                    "invite_link": existing.invite_link,
                    "error": None,
                })

                continue

            link_result = await self._create_link_with_retry(bot, channel)

            if link_result["invite_link"]:

                self.repository.create(
                    db,
                    TelegramInviteLink(
                        user_id=user_id,
                        channel_id=channel.id,
                        invite_link=link_result["invite_link"],
                        member_limit=1,
                    ),
                )

            results.append({
                "channel_name": channel.name,
                "invite_link": link_result["invite_link"],
                "error": link_result["error"],
            })

        return results

    async def _create_link_with_retry(self, bot: Bot, channel) -> dict:

        last_error = None

        attempts = len(RETRY_DELAYS_SECONDS) + 1

        for attempt in range(attempts):

            try:

                chat_invite_link = await bot.create_chat_invite_link(
                    chat_id=int(channel.chat_id),
                    name=f"invite-{channel.name}",
                    member_limit=1,
                )

                return {
                    "invite_link": chat_invite_link.invite_link,
                    "error": None,
                }

            except TelegramAPIError as exc:

                last_error = str(exc)

                logger.error(
                    "Invite link creation failed (attempt %s/%s) "
                    "for channel_id=%s (%s): %s",
                    attempt + 1, attempts, channel.id, channel.name, last_error,
                )

                if attempt < len(RETRY_DELAYS_SECONDS):
                    await asyncio.sleep(RETRY_DELAYS_SECONDS[attempt])

        return {"invite_link": None, "error": last_error}
