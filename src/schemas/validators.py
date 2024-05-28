from datetime import datetime
from typing import Annotated

from pydantic import BeforeValidator, AfterValidator


def empty_str_to_none(value: str):
    return None if value == '' else value


EmptyStrToNone = Annotated[str | None, BeforeValidator(empty_str_to_none)]


def normalize_date_time(value: datetime):
    return value.isoformat(sep=' ', timespec='seconds') if value else None


DateTimeNormalized = Annotated[datetime | None, AfterValidator(normalize_date_time)]
