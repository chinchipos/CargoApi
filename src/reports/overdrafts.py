from typing import List

from src.database.model.models import OverdraftsHistory as OverdraftsHistoryOrm
from src.reports.base import BaseExcelReport, ExcelDataType, ExcelAlign


class OverdraftsReport(BaseExcelReport):

    def make_excel(self, overdrafts: List[OverdraftsHistoryOrm]):
        worksheet = self.workbook.add_worksheet('Овердрафты')
        worksheet.freeze_panes(1, 0)

        # Инициализируем настройки таблицы
        columns = [
            dict(
                title='ИНН',
                width=13,
                cell_format=self.format(data_type=ExcelDataType.INTEGER),
            ),
            dict(
                title='Наименование',
                width=50,
                cell_format=self.format(),
            ),
            dict(
                title='Сумма долга',
                width=15,
                cell_format=self.format(data_type=ExcelDataType.FLOAT_SEPARATED, align=ExcelAlign.RIGHT),
            ),
            dict(
                title='Согласованная сумма овердрафта',
                width=20,
                cell_format=self.format(data_type=ExcelDataType.FLOAT_SEPARATED, align=ExcelAlign.RIGHT),
            ),
            dict(
                title='Дата отключения услуги',
                width=17,
                cell_format=self.format(align=ExcelAlign.CENTER),
            ),
        ]

        # Записывем заголовки таблицы
        row = 0
        for column_index, column in enumerate(columns):
            worksheet.write(row, column_index, column['title'], self.title_format)
            worksheet.set_column(column_index, column_index, column['width'])

        # Заполняем таблицу данными
        row += 1
        for overdraft in overdrafts:
            values = [
                # ИНН
                overdraft.balance.company.inn,
                # Наименование
                overdraft.balance.company.name,
                # Сумма долга
                overdraft.balance.balance,
                # Согласованная сумма овердрафта
                overdraft.sum,
                # Дата отключения услуги
                overdraft.end_date.isoformat()
            ]

            for col in range(0, len(values)):
                worksheet.write(row, col, values[col], columns[col]['cell_format'])

            row += 1

        # Автофильтр
        worksheet.autofilter(0, 0, row, len(columns) - 1)

        self.workbook.close()
        return self.output.getvalue()
