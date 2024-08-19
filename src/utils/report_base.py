import io
from enum import Enum
from typing import Dict

import xlsxwriter
from xlsxwriter.format import Format


class ExcelDataType(Enum):
    UNDEFINED = {}
    INTEGER = {'num_format': '###0'}
    INTEGER_SEPARATED = {'num_format': '# ##0'}
    FLOAT = {'num_format': '###0.00'}
    FLOAT_SEPARATED = {'num_format': '# ##0.00'}


class ExcelAlign(Enum):
    LEFT = {'align': 'left'}
    CENTER = {'align': 'center'}
    RIGHT = {'align': 'right'}


class BaseExcelReport:

    def __init__(self):
        self.protect_options = {
            'objects': False,
            'scenarios': False,
            'format_cells': True,
            'format_columns': True,
            'format_rows': True,
            'insert_columns': False,
            'insert_rows': False,
            'insert_hyperlinks': False,
            'delete_columns': False,
            'delete_rows': False,
            'select_locked_cells': True,
            'sort': True,
            'autofilter': True,
            'pivot_tables': False,
            'select_unlocked_cells': True,
        }
        self.password = '12345'
        self.output = io.BytesIO()
        self.workbook = xlsxwriter.Workbook(self.output)
        self.title_format = self.workbook.add_format(
            {'bold': True, 'border': 1, 'text_wrap': True, 'valign': 'top', 'locked': False})
        self.common_cell_format = {'border': 1, 'text_wrap': True, 'valign': 'vcenter'}

    def format(self, data_type: ExcelDataType | None = None, align: ExcelAlign | None = None,
               bg_color: Dict[str, str] | None = None) -> Format:
        if not data_type:
            data_type = ExcelDataType.UNDEFINED

        if not align:
            align = ExcelAlign.LEFT

        if not bg_color:
            bg_color = {}

        return self.workbook.add_format(data_type.value | align.value | bg_color | self.common_cell_format)
