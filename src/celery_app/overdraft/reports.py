from datetime import timedelta, datetime, date
from typing import List, Tuple

from src.config import TZ
from src.database.models.overdrafts_history import OverdraftsHistoryOrm
from src.database.models.transaction import TransactionOrm
from src.utils.report_base import BaseExcelReport, ExcelDataType, ExcelAlign


class OverdraftsReport(BaseExcelReport):

    def make_excel(self, overdrafts: List[Tuple[OverdraftsHistoryOrm, TransactionOrm]]):
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
                title='Согласованная сумма овердрафта',
                width=20,
                cell_format=self.format(data_type=ExcelDataType.FLOAT_SEPARATED, align=ExcelAlign.RIGHT),
            ),
            dict(
                title='Сумма долга',
                width=15,
                cell_format=self.format(data_type=ExcelDataType.FLOAT_SEPARATED, align=ExcelAlign.RIGHT),
            ),
            dict(
                title='Согласованный срок овердрафта',
                width=19,
                cell_format=self.format(data_type=ExcelDataType.INTEGER, align=ExcelAlign.RIGHT),
            ),
            dict(
                title='Дата открытия овердрафта',
                width=17,
                cell_format=self.format(align=ExcelAlign.CENTER),
            ),
            dict(
                title='Дата отключения услуги и блокировки карт',
                width=23,
                cell_format=self.format(align=ExcelAlign.CENTER),
            ),
            dict(
                title='Кол-во дней просрочки',
                width=13,
                cell_format=self.format(data_type=ExcelDataType.INTEGER, align=ExcelAlign.CENTER),
            ),
        ]

        # Записывем заголовки таблицы
        row = 0
        for column_index, column in enumerate(columns):
            worksheet.write(row, column_index, column['title'], self.title_format)
            worksheet.set_column(column_index, column_index, column['width'])

        # Заполняем таблицу данными
        row += 1
        for overdraft_data in overdrafts:
            overdraft = overdraft_data[0]
            last_transaction = overdraft_data[1]
            blocking_cards_date: date = overdraft.begin_date + timedelta(days=overdraft.days + 1)
            today = datetime.now(tz=TZ).date()
            overdue_days = (today - blocking_cards_date).days + 1 if blocking_cards_date <= today else None
            values = [
                # ИНН
                overdraft.balance.company.inn,
                # Наименование
                overdraft.balance.company.name,
                # Согласованная сумма овердрафта
                overdraft.sum,
                # Сумма долга
                last_transaction.company_balance,
                # Согласованный срок овердрафта
                overdraft.days,
                # Дата открытия овердрафта
                overdraft.begin_date.isoformat(),
                # Дата отключения услуги и блокировки карт
                blocking_cards_date.isoformat(),
                # Кол-во дней просрочки
                overdue_days
            ]

            for col in range(0, len(values)):
                worksheet.write(row, col, values[col], columns[col]['cell_format'])

            row += 1

        # Автофильтр
        worksheet.autofilter(0, 0, row, len(columns) - 1)

        self.workbook.close()
        return self.output.getvalue()
