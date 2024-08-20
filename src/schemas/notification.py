from datetime import date, datetime
from typing import Annotated

from pydantic import Field

from src.schemas.base import BaseSchema

id_ = Annotated[str, Field(description="UUID ассылки", examples=["20f06bf0-ae28-4f32-b2ca-f57796103a71"])]
date_time_read_ = Annotated[datetime | None, Field(description="Время прочтения", examples=["2023-05-17 12:57:43"])]
date_create_ = Annotated[date, Field(description="Дата создания", examples=["2023-05-17"])]
caption_ = Annotated[str, Field(description="Заголовок уведомления", examples=["Замена карт на новые"])]
text_ = Annotated[str, Field(description="Текст уведомления", examples=["Замена карт на новые"])]


class NotifcationReadSchema(BaseSchema):
    date_create: date_create_
    caption: caption_
    text: text_


class NotifcationMailingReadSchema(BaseSchema):
    id: id_
    date_time_read: date_time_read_
    notification: Annotated[NotifcationReadSchema, Field(description="Уведомление")]
