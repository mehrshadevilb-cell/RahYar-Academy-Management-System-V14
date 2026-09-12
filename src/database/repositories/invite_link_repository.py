from sqlalchemy.orm import Session

from src.database.models.invite_link import TelegramInviteLink


class InviteLinkRepository:

    def create(
        self,
        db: Session,
        invite: TelegramInviteLink,
    ) -> TelegramInviteLink:

        db.add(invite)
        db.commit()
        db.refresh(invite)

        return invite

    def get_by_user_and_channel(
        self,
        db: Session,
        user_id: int,
        channel_id: int,
    ) -> TelegramInviteLink | None:

        return (
            db.query(TelegramInviteLink)
            .filter(
                TelegramInviteLink.user_id == user_id,
                TelegramInviteLink.channel_id == channel_id,
            )
            .first()
        )
