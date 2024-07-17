from copy import deepcopy
from typing import List

from sqlalchemy import select as sa_select, func as sa_func, null
from sqlalchemy.orm import aliased

from src.database.models import System as SystemOrm, CardBinding as CardBindingOrm
from src.repositories.base import BaseRepository


class SystemRepository(BaseRepository):

    async def get_system(self, system_id: str) -> SystemOrm:
        system_table_total = aliased(SystemOrm, name="system_table_total")
        system_table_in_use = aliased(SystemOrm, name="system_table_in_use")
        system_table = aliased(SystemOrm, name="system_table")

        subq_cards_total = (
            sa_select(
                system_table_total.id,
                sa_func.count(CardBindingOrm.id).label('cards_amount_total'),
            )
            .where(system_table_total.id == system_id)
            .where(CardBindingOrm.system_id == system_table_total.id)
            .group_by(system_table_total.id)
            .subquery("helper_cards_total")
        )

        subq_cards_in_use = (
            sa_select(
                system_table_in_use.id,
                sa_func.count(CardBindingOrm.id).label('cards_amount_in_use'),
            )
            .where(system_table_in_use.id == system_id)
            .where(CardBindingOrm.system_id == system_table_in_use.id)
            .where(CardBindingOrm.balance_id.is_not(null()))
            .group_by(system_table_in_use.id)
            .subquery("helper_cards_in_use")
        )

        stmt_get_system = (
            sa_select(
                system_table,
                subq_cards_total.c.cards_amount_total,
                subq_cards_in_use.c.cards_amount_in_use
            )
            .select_from(subq_cards_total, subq_cards_in_use, system_table)
            .where(system_table.id == system_id)
            .where(subq_cards_total.c.id == system_table.id)
            .where(subq_cards_in_use.c.id == system_table.id)

        )

        dataset = await self.select_first(stmt_get_system, scalars=False)
        system = dataset[0]
        system.annotate({'cards_amount_total': dataset[1]})
        system.annotate({'cards_amount_in_use': dataset[2]})
        system.annotate({'cards_amount_free': dataset[1] - dataset[2]})
        return system

    """
    async def create(self, create_schema: SystemCreateSchema) -> SystemOrm:
        new_system = SystemOrm(**create_schema.model_dump())
        await self.save_object(new_system)
        new_system = await self.get_system(new_system.id)
        return new_system
    """

    async def get_systems(self) -> List[SystemOrm]:
        system_table_total = aliased(SystemOrm, name="system_table_total")
        system_table_in_use = aliased(SystemOrm, name="system_table_in_use")
        system_table = aliased(SystemOrm, name="system_table")

        subq_cards_total = (
            sa_select(
                system_table_total.id,
                sa_func.count(CardBindingOrm.id).label('cards_amount_total'),
            )
            .where(CardBindingOrm.system_id == system_table_total.id)
            .group_by(system_table_total.id)
            .subquery("helper_cards_total")
        )

        subq_cards_in_use = (
            sa_select(
                system_table_in_use.id,
                sa_func.count(CardBindingOrm.id).label('cards_amount_in_use'),
            )
            .where(CardBindingOrm.system_id == system_table_in_use.id)
            .where(CardBindingOrm.balance_id.is_not(null()))
            .group_by(system_table_in_use.id)
            .subquery("helper_cards_in_use")
        )

        stmt_get_systems = (
            sa_select(
                system_table,
                subq_cards_total.c.cards_amount_total,
                subq_cards_in_use.c.cards_amount_in_use
            )
            .select_from(subq_cards_total, subq_cards_in_use, system_table)
            .where(subq_cards_total.c.id == system_table.id)
            .where(subq_cards_in_use.c.id == system_table.id)
        )

        dataset = await self.select_all(stmt_get_systems, scalars=False)

        def annotate_amounts(data):
            data[0].annotate({'cards_amount_total': data[1]})
            data[0].annotate({'cards_amount_in_use': data[2]})
            data[0].annotate({'cards_amount_free': data[1] - data[2]})
            return data[0]

        systems = list(map(annotate_amounts, dataset))
        return systems

    async def get_cards_amount(self, system_id: str) -> int:
        stmt = (
            sa_select(sa_func.count(CardBindingOrm.id))
            .select_from(CardBindingOrm)
            .where(CardBindingOrm.system_id == system_id)
        )
        amount = await self.select_single_field(stmt)
        return amount

    async def get_system_by_short_name(self, system_fhort_name: str) -> SystemOrm:
        stmt = sa_select(SystemOrm).where(SystemOrm.short_name == system_fhort_name)
        system = await self.select_first(stmt)
        return system
