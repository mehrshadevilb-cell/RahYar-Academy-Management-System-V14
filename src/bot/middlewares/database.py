from aiogram import BaseMiddleware

from src.database.session import SessionLocal


class DatabaseMiddleware(BaseMiddleware):

    async def __call__(
        self,
        handler,
        event,
        data,
    ):

        db = SessionLocal()

        try:
            data["db"] = db

            return await handler(
                event,
                data,
            )

        finally:
            db.close()