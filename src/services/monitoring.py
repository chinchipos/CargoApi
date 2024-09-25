from typing import List

from src.database.models.check_report import CheckReport
from src.repositories.monitoring import MonitoringRepository
from src.schemas.monitoring import CheckReportSchema, CheckReportTypeSchema


class MonitoringService:

    def __init__(self, repository: MonitoringRepository) -> None:
        self.repository = repository
        self.logger = repository.logger

    async def get_reports(self) -> List[CheckReportTypeSchema]:
        reports = await self.repository.get_reports()
        output = []
        report_ids_to_delete = []
        for report in reports:
            report_version = {
                "id": report.id,
                "creation_time": report.creation_time.replace(microsecond=0)
            }
            found = False
            for report_type in output:
                if report_type["name"] == report.report_type.name:
                    # Храним не более 3-х вариантов каждого отчета
                    if len(report_type["versions"]) < 3:
                        report_type["versions"].append(report_version)
                    else:
                        report_ids_to_delete.append(report.id)
                    found = True
                    break

            if not found:
                report_type = {
                    "name": report.report_type.name,
                    "description": report.report_type.value["description"],
                    "versions": [report_version]
                }
                output.append(report_type)

        # Удаляем устаревшие отчеты
        if report_ids_to_delete:
            await self.repository.delete_reports(report_ids_to_delete)

        # report_list_schema = CheckReportListSchema.model_validate({"reports": output})
        data = [CheckReportTypeSchema.model_validate(item) for item in output]
        return data

    async def get_report(self, report_id: str) -> CheckReportSchema:
        check_report = await self.repository.get_report(report_id=report_id)
        output = {
            "id": check_report.id,
            "report_type": check_report.report_type.name,
            "description": check_report.report_type.value["description"],
            "creation_time": check_report.creation_time.replace(microsecond=0),
            "records": [record for record in check_report.data if record],
        }
        report_schema = CheckReportSchema.model_validate(output)
        return report_schema

    @staticmethod
    async def get_report_types() -> List[CheckReportTypeSchema]:
        data = [
            CheckReportTypeSchema(
                name=check_report.name,
                description=check_report.value["description"]
            ) for check_report in CheckReport
        ]
        return data
