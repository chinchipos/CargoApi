from datetime import date
from typing import List, Any

from fastapi import Depends, APIRouter

from src.depends import get_service_transaction
from src.schemas.transaction import TransactionReadSchema
from src.services.transaction import TransactionService
from src.utils.descriptions.transaction import transaction_tag_description, get_transactions_description
from src.utils.schemas import MessageSchema

router = APIRouter()
transaction_tag_metadata = {
    "name": "transaction",
    "description": transaction_tag_description,
}


@router.get(
    path="/transaction/month",
    tags=["transaction"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[TransactionReadSchema],
    name = 'Получение списка транзакций',
    description = get_transactions_description
)
async def get_transactions(
    end_date: date = date.today(),
    service: TransactionService = Depends(get_service_transaction)
) -> List[Any]:
    # Получать сведения может пользователь с любой ролью, но состав списка зависит от роли
    # пользователя. Проверка будет выполнена при формировании списка.
    transaction = await service.get_transactions(end_date)
    return transaction
