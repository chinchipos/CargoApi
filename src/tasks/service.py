from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update as sa_update

from src.database.models import Company


async def clear_old_temporary_overdrafts(session: AsyncSession) -> None:
    # Удаляем информацию о временном овердрафте, если дата его прекращения меньше текущей даты
    stmt = (
        sa_update(Company)
        .where(Company.min_balance_period_end_date < date.today())
        .values({
            "min_balance_on_period": 0,
            "min_balance_period_end_date": None
        })
    )
    await session.execute(stmt)
