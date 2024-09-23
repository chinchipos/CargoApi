from typing import List

from sqlalchemy import select as sa_select, delete as sa_delete, desc

from src.database.models.check_report import CheckReportOrm
from src.repositories.base import BaseRepository


class MonitoringRepository(BaseRepository):

    async def get_reports(self) -> List[CheckReportOrm]:
        stmt = (
            sa_select(CheckReportOrm)
            .order_by(
                CheckReportOrm.report_type,
                desc(CheckReportOrm.creation_time)
            )
        )
        reports = await self.select_all(stmt)
        return reports

    async def get_report(self, report_id: str) -> CheckReportOrm:
        stmt = sa_select(CheckReportOrm).where(CheckReportOrm.id == report_id)
        report = await self.select_first(stmt)
        return report

    async def delete_reports(self, report_ids: List[str]) -> None:
        stmt = sa_delete(CheckReportOrm).where(CheckReportOrm.id.in_(report_ids))
        await self.session.execute(stmt)
        await self.session.commit()
