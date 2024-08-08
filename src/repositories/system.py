from typing import List

from sqlalchemy import select as sa_select, func as sa_func, null

from src.database.model.card import CardOrm
from src.database.model.models import System as SystemOrm, CardSystem as CardSystemOrm
from src.repositories.base import BaseRepository
from src.utils.enums import ContractScheme


class SystemRepository(BaseRepository):

    async def get_system(self, system_id: str) -> SystemOrm:
        subq_cards_total = (
            sa_select(
                CardSystemOrm.system_id,
                sa_func.count(CardSystemOrm.id).label('cards_amount_total'),
            )
            .where(CardSystemOrm.system_id == system_id)
            .group_by(CardSystemOrm.system_id)
            .subquery("helper_cards_total")
        )

        subq_cards_in_use = (
            sa_select(
                CardSystemOrm.system_id,
                sa_func.count(CardSystemOrm.id).label('cards_amount_in_use'),
            )
            .where(CardOrm.company_id.is_not(null()))
            .where(CardSystemOrm.card_id == CardOrm.id)
            .where(CardSystemOrm.system_id == system_id)
            .group_by(CardSystemOrm.system_id)
            .subquery("helper_cards_in_use")
        )

        stmt = (
            sa_select(
                SystemOrm,
                subq_cards_total.c.cards_amount_total,
                subq_cards_in_use.c.cards_amount_in_use
            )
            .select_from(SystemOrm)
            .where(SystemOrm.id == system_id)
            .outerjoin(subq_cards_total, subq_cards_total.c.system_id == SystemOrm.id)
            .outerjoin(subq_cards_in_use, subq_cards_in_use.c.system_id == SystemOrm.id)
        )

        dataset = await self.select_first(stmt, scalars=False)
        system = dataset[0]
        system.annotate({'cards_amount_total': dataset[1]})
        system.annotate({'cards_amount_in_use': dataset[2]})
        system.annotate({'cards_amount_free': dataset[1] - dataset[2]})
        return system

    async def get_systems(self) -> List[SystemOrm]:
        subq_cards_total = (
            sa_select(
                CardSystemOrm.system_id,
                sa_func.count(CardSystemOrm.id).label('cards_amount_total'),
            )
            .group_by(CardSystemOrm.system_id)
            .subquery("helper_cards_total")
        )

        subq_cards_in_use = (
            sa_select(
                CardSystemOrm.system_id,
                sa_func.count(CardSystemOrm.id).label('cards_amount_in_use'),
            )
            .where(CardOrm.company_id.is_not(null()))
            .where(CardSystemOrm.card_id == CardOrm.id)
            .group_by(CardSystemOrm.system_id)
            .subquery("helper_cards_in_use")
        )

        stmt = (
            sa_select(
                SystemOrm,
                subq_cards_total.c.cards_amount_total,
                subq_cards_in_use.c.cards_amount_in_use
            )
            .select_from(SystemOrm)
            .outerjoin(subq_cards_total, subq_cards_total.c.system_id == SystemOrm.id)
            .outerjoin(subq_cards_in_use, subq_cards_in_use.c.system_id == SystemOrm.id)
            .where(SystemOrm.enabled)
        )

        dataset = await self.select_all(stmt, scalars=False)

        def annotate_amounts(data):
            cards_amount_total = data[1] if data[1] else 0
            cards_amount_in_use = data[2] if data[2] else 0
            cards_amount_free = cards_amount_total - cards_amount_in_use
            data[0].annotate({'cards_amount_total': cards_amount_total})
            data[0].annotate({'cards_amount_in_use': cards_amount_in_use})
            data[0].annotate({'cards_amount_free': cards_amount_free})
            return data[0]

        systems = list(map(annotate_amounts, dataset))
        return systems

    async def get_cards_amount(self, system_id: str) -> int:
        stmt = (
            sa_select(sa_func.count(CardSystemOrm.id))
            .select_from(CardSystemOrm)
            .where(CardSystemOrm.system_id == system_id)
        )
        amount = await self.select_single_field(stmt)
        return amount

    async def get_system_by_short_name(self, system_fhort_name: str, scheme: ContractScheme) -> SystemOrm:
        stmt = (
            sa_select(SystemOrm)
            .where(SystemOrm.short_name == system_fhort_name)
            .where(SystemOrm.scheme == scheme)
        )
        system = await self.select_first(stmt)
        return system
