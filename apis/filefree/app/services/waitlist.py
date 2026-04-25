"""medallion: ops"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.waitlist import Waitlist
from app.repositories.waitlist import WaitlistRepository
from app.schemas.waitlist import WaitlistCreate
from app.utils.exceptions import ConflictError


class WaitlistService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = WaitlistRepository(session)

    async def join_waitlist(self, data: WaitlistCreate) -> Waitlist:
        existing = await self.repo.get_by_email(str(data.email))
        if existing:
            raise ConflictError("This email is already on the waitlist")

        return await self.repo.create(
            email=str(data.email),
            source=data.source,
            attribution=data.attribution,
        )
