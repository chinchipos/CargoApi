import uuid
from typing import List, Any

from fastapi import APIRouter, Depends

from src.database import models
from src.depends import get_service_company
from src.schemas.common import ModelIDSchema
from src.schemas.company import CompanyReadSchema, CompanyEditSchema
from src.services.company import CompanyService
from src.utils.descriptions.company import company_tag_description, edit_company_description, get_company_description, \
    get_companies_description
from src.utils.schemas import MessageSchema

router = APIRouter()
company_tag_metadata = {
    "name": "company",
    "description": company_tag_description,
}


@router.post(
    path="/company/edit",
    tags=["company"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = CompanyReadSchema,
    description = edit_company_description
)
async def edit(
    data: CompanyEditSchema,
    service: CompanyService = Depends(get_service_company)
):
    company = await service.edit(data)
    return company


@router.get(
    path="/company/get_company/{company_id}",
    tags=["company"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = CompanyReadSchema,
    description = get_company_description
)
async def get_company(
    company_id: uuid.UUID,
    service: CompanyService = Depends(get_service_company)
) -> Any:
    company = await service.get_company(str(company_id))
    return company


@router.get(
    path="/company/get_companies",
    tags=["company"],
    responses = {400: {'model': MessageSchema, "description": "Bad request"}},
    response_model = List[CompanyReadSchema],
    description = get_companies_description
)
async def get_companies(
    service: CompanyService = Depends(get_service_company)
) -> List[Any]:
    company = await service.get_companies()
    return company
