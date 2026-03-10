from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.waitlist import Waitlist
from app.repositories.base import BaseRepository


class WaitlistRepository(BaseRepository[Waitlist]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Waitlist, session)

    async def get_by_email(self, email: str) -> Waitlist | None:
        result = await self.session.execute(select(Waitlist).where(Waitlist.email == email))
        return result.scalar_one_or_none()
