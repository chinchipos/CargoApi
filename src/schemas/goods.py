from typing import Annotated, List

from pydantic import Field

from src.database.models.goods_category import GoodsCategory
from src.schemas.base import BaseSchema
from src.schemas.system import SystemReadMinimumSchema
from src.schemas.validators import EmptyStrToNone

inner_goods_id_ = Annotated[
    str, Field(description="UUID товара/услуги в локальной системе",
               examples=["68425199-ac93-4733-becb-de2e89e85303"])]

inner_goods_name_ = Annotated[EmptyStrToNone, Field(description="Локальное наименование", examples=["ДТ-З-К5"])]

outer_goods_id_ = Annotated[
    str, Field(description="UUID записи о продукте из системы поставщика",
               examples=["03aa8565-e701-4501-86a9-cc8c9c99ecb7"])]

goods_external_id_ = Annotated[
    str | None, Field(description="ID продукта в системе поставщика услуг",
                      examples=["000000006"])]

outer_goods_name_ = Annotated[str, Field(description="Наименование в системе поставщика услуг", examples=["ДТЗК5"])]

system_ = Annotated[SystemReadMinimumSchema | None, Field(description="Поставщик услуг")]

inner_group_id_ = Annotated[str | None, Field(
    description="UUID группы продуктов в нашей системе",
    examples=["68425199-ac93-4733-becb-de2e89e85303"]
)]

inner_group_name_ = Annotated[
    str, Field(description="Наименование группы продуктов в нашей системе", examples=["Уход за автомобилем"])]

outer_category_id_ = Annotated[
    str, Field(description="UUID категории продуктов в системе поставщика",
               examples=["68425199-ac93-4733-becb-de2e89e85303"])]

outer_category_name_ = Annotated[
    str, Field(description="Наименование категории продуктов в системе поставщика", examples=["NON-FOOD"])]

outer_group_id_ = Annotated[
    str, Field(description="UUID группы продуктов в системе поставщика",
               examples=["68425199-ac93-4733-becb-de2e89e85303"])]

outer_group_name_ = Annotated[
    str, Field(description="Наименование группы продуктов в системе поставщика", examples=["Уход за автомобилем"])]

inner_category_ = Annotated[
    GoodsCategory | None,
    Field(description="Категория продуктов в нашей системе", examples=["Топливо"])
]


class InnerGoodsGroupReadSchema(BaseSchema):
    id: inner_group_id_
    name: inner_group_name_
    inner_category: inner_category_ = None


class OuterGoodsCategoryReadSchema(BaseSchema):
    id: outer_category_id_
    name: outer_category_name_


class OuterGoodsGroupReadSchema(BaseSchema):
    id: outer_group_id_
    name: outer_group_name_
    inner_group: Annotated[
        InnerGoodsGroupReadSchema | None, Field(description="Группа продуктов в нашей системе")] = None
    outer_category: Annotated[
        OuterGoodsCategoryReadSchema | None, Field(description="Категория продуктов в системе поставщика")] = None


class InnerGoodsReadSchema(BaseSchema):
    id: inner_goods_id_
    name: inner_goods_name_
    inner_goods: Annotated[
        InnerGoodsGroupReadSchema | None, Field(description="Группа продуктов в нашей системе")] = None


class InnerGoodsEditSchema(BaseSchema):
    inner_name: inner_goods_name_
    inner_group_id: inner_group_id_ = None


class OuterGoodsItemReadSchema(BaseSchema):
    id: outer_goods_id_
    external_id: goods_external_id_ = None
    name: outer_goods_name_
    inner_name: inner_goods_name_
    outer_group: Annotated[
        OuterGoodsGroupReadSchema | None, Field(description="Группа продуктов в системе поставщика")] = None
    system: system_ = None


class GoodsDictionariesSchema(BaseSchema):
    inner_names: Annotated[List[str], Field(description="Наименования продуктов в системе ННК")]
    inner_groups: Annotated[List[InnerGoodsGroupReadSchema], Field(description="Тарифные политики")]


class OuterGoodsReadSchema(BaseSchema):
    outer_goods: Annotated[List[OuterGoodsItemReadSchema], Field(description="Организации")]
    dictionaries: Annotated[GoodsDictionariesSchema | None, Field(description="Справочники")] = None
