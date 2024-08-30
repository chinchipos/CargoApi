from datetime import datetime
from typing import List

from fastapi import Depends, APIRouter

from src.depends import get_service_transaction
from src.descriptions.transaction import transaction_tag_description, get_transactions_description
from src.schemas.transaction import TransactionReadSchema
from src.services.transaction import TransactionService
from src.utils.schemas import MessageSchema

router = APIRouter()
transaction_tag_metadata = {
    "name": "transaction",
    "description": transaction_tag_description,
}


@router.get(
    path="/transaction/list",
    tags=["transaction"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[TransactionReadSchema],
    summary = 'Получение списка транзакций',
    description = get_transactions_description
)
async def get_transactions(
    company_id: str | None = None,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
    service: TransactionService = Depends(get_service_transaction)
):
    # Получать сведения может пользователь с любой ролью, но состав списка зависит от роли
    # пользователя. Проверка будет выполнена при формировании списка.
    transaction = await service.get_transactions(company_id, from_dt, to_dt)
    return transaction
