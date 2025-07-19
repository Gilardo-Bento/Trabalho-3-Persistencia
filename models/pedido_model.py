from enum import Enum
from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from bson import ObjectId
from all_enum.status_enum import StatusPedido, FormaPagamento
from models.base import PyObjectId

class ItemPedido(BaseModel):
    id_produto: PyObjectId
    nome_produto: str
    sku_selecionado: Optional[str]
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

class PedidoOut(PedidoBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")

    class Config:
        populate_by_name = True  
        json_encoders = {ObjectId: str}

class ItemPedidoCreate(BaseModel):
    """
    Modelo simplificado para um item no momento da criação do pedido.
    O cliente só precisa informar o SKU e a quantidade.
    """
    sku_selecionado: str = Field(..., description="O SKU único da variação do produto a ser comprada.")
    quantidade: int = Field(..., gt=0, description="A quantidade de itens a serem comprados. Deve ser maior que zero.")

class PedidoCreate(BaseModel):
    """
    Modelo simplificado para a criação de um novo pedido.
    """
    id_usuario: str = Field(..., description="ID do usuário que está fazendo o pedido.")
    status: StatusPedido = Field(default=StatusPedido.PENDENTE, description="Status inicial do pedido.")
    forma_pagamento: FormaPagamento = Field(..., description="Forma de pagamento escolhida.")
    itens: List[ItemPedidoCreate] = Field(..., description="Lista de itens do pedido.")
