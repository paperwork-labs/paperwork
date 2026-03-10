import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.filing import Filing, FilingStatus
from app.repositories.base import BaseRepository


class FilingRepository(BaseRepository[Filing]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Filing, session)

    async def get_by_id_with_relations(
        self, filing_id: uuid.UUID
    ) -> Filing | None:
        result = await self.session.execute(
            select(Filing)
            .where(Filing.id == filing_id)
            .options(
                selectinload(Filing.documents),
                selectinload(Filing.tax_profile),
                selectinload(Filing.tax_calculation),
            )
        )
        return result.scalars().first()

    async def get_user_filings(
        self, user_id: uuid.UUID, tax_year: int | None = None
    ) -> list[Filing]:
        stmt = select(Filing).where(Filing.user_id == user_id)
        if tax_year:
            stmt = stmt.where(Filing.tax_year == tax_year)
        stmt = stmt.order_by(Filing.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_filing(
        self, user_id: uuid.UUID, tax_year: int
    ) -> Filing | None:
        result = await self.session.execute(
            select(Filing)
            .where(
                Filing.user_id == user_id,
                Filing.tax_year == tax_year,
                Filing.status.notin_([
                    FilingStatus.ACCEPTED,
                    FilingStatus.REJECTED,
                ]),
            )
            .order_by(Filing.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()
