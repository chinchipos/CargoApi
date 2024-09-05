from typing import List, Dict, Any

from src.utils.report_base import BaseExcelReport

import os


class ExportToExcel(BaseExcelReport):

    def make_excel(self, data: List[Dict[str, Any]], headers: List[str], filename: str, export_dir: str) -> None:
        worksheet_title = filename.split(".")[0]
        worksheet = self.workbook.add_worksheet(worksheet_title)
        worksheet.freeze_panes(1, 0)

        # Инициализируем настройки таблицы
        columns = [
            {
                "title": header,
                "width": 15,
                "cell_format": self.format(),
            } for header in headers
        ]

        # Записывем заголовки таблицы
        row = 0
        for column_index, column in enumerate(columns):
            worksheet.write(row, column_index, column['title'], self.title_format)
            worksheet.set_column(column_index, column_index, column['width'])

        # Заполняем таблицу данными
        row += 1
        for e in data:
            values = [v for k, v in e.items()]
            for col in range(0, len(values)):
                worksheet.write(row, col, str(values[col]), columns[col]['cell_format'])

            row += 1

        # Автофильтр
        worksheet.autofilter(0, 0, row, len(columns) - 1)

        self.workbook.close()

        # Запись в файл
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)

        with open(os.path.join(export_dir, filename), "wb") as f:
            f.write(self.output.getvalue())

        print("Данные экспортированы в файл")
