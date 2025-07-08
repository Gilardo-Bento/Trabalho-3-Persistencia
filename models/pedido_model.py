
from enum import Enum
from datetime import datetime
from typing import List, Dict
from pydantic import BaseModel, Field
from bson import ObjectId
from all_enum.status_enum import StatusPedido, FormaPagamento
from models.base import PyObjectId

class ItemPedido(BaseModel):
    id_produto: PyObjectId
    nome_produto: str
    sku_selecionado: str
    atributos_selecionados: Dict[str, str]
    quantidade: int
    preco_unitario: float

    class Config:
        json_encoders = {ObjectId: str}

class PedidoBase(BaseModel):
    id_usuario: PyObjectId
    data_pedido: datetime
    valor_total: float
    status: StatusPedido
    forma_pagamento: FormaPagamento
    itens: List[ItemPedido] = Field(default_factory=list)

class PedidoCreate(PedidoBase):
    pass

class PedidoOut(PedidoBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")

    class Config:
        populate_by_name = True  # Para compatibilidade com alias no FastAPI
        json_encoders = {ObjectId: str}
