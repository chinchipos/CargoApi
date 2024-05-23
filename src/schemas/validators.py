from typing import Annotated

from pydantic import BeforeValidator


def empty_str_to_none(value: str):
    return None if value == '' else value


EmptyStrToNone = Annotated[str | None, BeforeValidator(empty_str_to_none)]
