from datetime import date
from typing import List, Annotated

from pydantic import Field

from src.schemas.balance import BalanceReadSchema
from src.schemas.base import BaseSchema
from src.schemas.notification import NotifcationMailingReadSchema
from src.schemas.role import RoleReadMinimumSchema
from src.schemas.tariff import TariffPolicyReadSchema
from src.schemas.validators import NegativeToPositive, PositiveToNegative
from src.utils.enums import Finance as FinanceEnum


class CompanyUserSchema(BaseSchema):
    id: Annotated[str, Field(description="UUID пользователя", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]
    username: Annotated[str, Field(description="Имя пользователя", examples=["user"])]
    first_name: Annotated[str, Field(description="Имя", examples=["Алексей"])]
    last_name: Annotated[str, Field(description="Фамилия", examples=["Гагарин"])]
    phone: Annotated[str, Field(description="Телефон", examples=["+79332194370"])]
    role: Annotated[RoleReadMinimumSchema, Field(description="Роль")]


class CompanyCarSchema(BaseSchema):
    id: Annotated[str, Field(description="UUID автомобиля", examples=["c39e5c5c-b980-45eb-a192-585e6823faa7"])]
    model: Annotated[str, Field(description="Марка/модель", examples=["Камаз"])]
    reg_number: Annotated[str, Field(description="Государственный регистрационный номер", examples=["Н314УР77"])]


id_ = Annotated[str, Field(description="UUID организации", examples=["20f06bf0-ae28-4f32-b2ca-f57796103a71"])]

name_ = Annotated[str | None, Field(description="Наименование", examples=['ООО "Современные технологии"'])]

inn_ = Annotated[str | None, Field(description="ИНН", examples=["77896534678800"])]

contract_number_ = Annotated[str | None, Field(description="Номер договора", max_length=100)]

min_balance_ = Annotated[
    PositiveToNegative | None,
    Field(description="Минимальный баланс, руб.", examples=[20000.0])]

contacts_ = Annotated[str | None, Field(description="Контактные данные", examples=[""])]

personal_account_ = Annotated[str | None, Field(description="Лицевой счет", examples=["6590100"])]

date_add_ = Annotated[date | None, Field(description="Дата добавления в систему", examples=["2023-05-17"])]

cards_amount_ = Annotated[
    int | None,
    Field(description="Количество карт, принадлежащих этой организации", examples=[60])]

users_ = Annotated[List[CompanyUserSchema], Field(description="Список пользователей этой организации")]

balances_ = Annotated[List[BalanceReadSchema], Field(description="Список балансов этой организации")]

cars_ = Annotated[List[CompanyCarSchema], Field(description="Список пользователей этой организации")]

direction_ = Annotated[
    FinanceEnum,
    Field(description="Операция дебетования/кредитования", examples=[FinanceEnum.DEBIT.value])]

delta_sum_ = Annotated[NegativeToPositive, Field(description="Сумма корректировки, руб", examples=[5000.0], gt=0)]

overdraft_on_ = Annotated[bool | None, Field(description='Услуга "Овердрафт" подключена', examples=[True])]

overdraft_sum_in_ = Annotated[
    PositiveToNegative | None,
    Field(description="Сумма овердрафта, руб.", examples=[20000.0])]

overdraft_sum_out_ = Annotated[
    NegativeToPositive | None,
    Field(description="Сумма овердрафта, руб.", examples=[20000.0])]

overdraft_days_ = Annotated[NegativeToPositive, Field(description="Срок овердрафта, дни", examples=[7])]

overdraft_fee_percent_ = Annotated[
    NegativeToPositive | None,
    Field(description="Комиссия за овердрафт, руб.", examples=[20000.0])]

overdraft_begin_date_ = Annotated[
    date | None,
    Field(description="Дата начала периода действия овердрафта", examples=["2023-05-17"])]

overdraft_end_date_ = Annotated[
    date | None,
    Field(description="Дата прекращения периода действия овердрафта", examples=["2023-05-21"])]

overdraft_payment_deadline_ = Annotated[
    date | None,
    Field(description="Крайняя дата погашения задолженности по овердрафту", examples=["2023-05-22"])]

# tariffs_ = Annotated[List[Dict[str, str]], Field(description="Тарифы систем")]
tariff_policy_id_ = Annotated[str, Field(description="UUID тарифной политики")]

notification_mailings_ = Annotated[List[NotifcationMailingReadSchema] | None, Field(description="Список уведомлений")]

tariff_policy_ = Annotated[TariffPolicyReadSchema | None, Field(description="Тарифная политика")]


class CompanyCreateSchema(BaseSchema):
    name: name_
    inn: inn_
    contract_number: contract_number_
    min_balance: min_balance_ = 0
    contacts: contacts_ = None
    overdraft_on: overdraft_on_ = False
    overdraft_sum: overdraft_sum_in_ = 0
    overdraft_days: overdraft_days_ = 0
    overdraft_fee_percent: overdraft_fee_percent_ = 0.074
    tariff_policy_id: tariff_policy_id_


class CompanyEditSchema(BaseSchema):
    name: name_ = None
    inn: inn_ = None
    contract_number: contract_number_ = None
    min_balance: min_balance_ = None
    contacts: contacts_ = None
    overdraft_on: overdraft_on_ = None
    overdraft_sum: overdraft_sum_in_ = None
    overdraft_days: overdraft_days_ = None
    overdraft_fee_percent: overdraft_fee_percent_ = None
    tariff_policy_id: tariff_policy_id_


class CompanyReadMinimumSchema(BaseSchema):
    id: id_
    name: name_
    inn: inn_
    personal_account: personal_account_


class CompanyReadSchema(BaseSchema):
    id: id_
    name: name_
    inn: inn_
    contract_number: contract_number_
    min_balance: min_balance_
    personal_account: personal_account_
    date_add: date_add_
    contacts: contacts_
    cards_amount: cards_amount_ = None
    overdraft_on: overdraft_on_
    overdraft_sum: overdraft_sum_out_
    overdraft_days: overdraft_days_
    overdraft_fee_percent: overdraft_fee_percent_
    users: users_ = []
    balances: balances_ = []
    cars: cars_ = []
    overdraft_begin_date: overdraft_begin_date_ = None
    overdraft_end_date: overdraft_end_date_ = None
    overdraft_payment_deadline: overdraft_payment_deadline_ = None
    notification_mailings: notification_mailings_ = None
    tariff_policy: tariff_policy_ = None


class CompanyBalanceEditSchema(BaseSchema):
    direction: direction_
    delta_sum:  delta_sum_


class CompanyDictionariesSchema(BaseSchema):
    tariff_polices: Annotated[List[TariffPolicyReadSchema] | None, Field(description="Тарифные политики")] = None


class CompaniesReadSchema(BaseSchema):
    companies: Annotated[List[CompanyReadSchema] | List[CompanyReadMinimumSchema], Field(description="Организации")]
    dictionaries: Annotated[CompanyDictionariesSchema | None, Field(description="Справочники")] = None
