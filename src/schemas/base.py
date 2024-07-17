from typing import Dict, Any

from pydantic import BaseModel, ConfigDict, model_serializer, Extra


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra=Extra.ignore
    )

    # При формировании JSON словаря первым будет идти ключ id, остальные будут отсортированы в порядке возрастания
    @model_serializer(when_used='json')
    def sort_model(self) -> Dict[str, Any]:
        model_dump = self.model_dump()
        output = {"id": model_dump.pop("id")} if "id" in model_dump else {}
        output |= dict(sorted(model_dump.items()))
        return output
