
from enum import Enum
from datetime import datetime
from typing import List
from pydantic import BaseModel, Field
from bson import ObjectId
from pydantic import ConfigDict
from models.base import PyObjectId
from all_enum.status_enum import TipoDesconto

class PromocaoBase(BaseModel):
    nome: str
    data_inicio: datetime
    data_fim: datetime
    tipo_desconto: TipoDesconto
    valor_desconto: float
    produtos_aplicaveis: List[PyObjectId] = Field(
        default_factory=list,
        example=[
            "68655fc79f4575ca35221b70",
            "68655fc79f4575ca35221b71"
        ]
    )

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

class PromocaoCreate(PromocaoBase):
    pass

class PromocaoOut(PromocaoBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")