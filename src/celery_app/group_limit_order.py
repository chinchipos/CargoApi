from typing import List
from src.database.models import GroupLimitOrm, CompanyOrm
from src.database.models.goods_category import GoodsCategory


class GroupLimitOrder:

    def __init__(self, personal_account: str, delta_sum: float = 0):
        self.personal_account = personal_account
        self.delta_sum = delta_sum
        self.company: CompanyOrm | None = None
        self.local_group_limits: List[GroupLimitOrm] = []
