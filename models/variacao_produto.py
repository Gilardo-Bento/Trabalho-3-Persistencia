

# models/variacao.py
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from bson import ObjectId
from models.base import PyObjectId

class VariacaoBase(BaseModel):
    produto_id: PyObjectId  # referência ao produto
    sku: str
    atributos: Dict[str, str]
    preco_adicional: float
    estoque: int
    urls_imagens: List[str]

class VariacaoCreate(VariacaoBase):
    pass

class VariacaoOut(VariacaoBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")

    class Config:
        json_encoders = {ObjectId: str}
        populate_by_name = True
