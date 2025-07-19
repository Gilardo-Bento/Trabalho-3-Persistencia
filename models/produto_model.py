from datetime import datetime
from bson import ObjectId
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from all_enum.status_enum import CategoriaProduto
from models.base import PyObjectId

class ProdutoBase(BaseModel):
    nome: str
    descricao: str
    preco_base: float
    categoria: CategoriaProduto
    data_de_cadastro: Optional[datetime] = None  
    estoque: int = 0   
    marca: Optional[str] = None

class ProdutoCreate(ProdutoBase):
    pass

class ProdutoOut(ProdutoBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")

    class Config:
        json_encoders = {ObjectId: str}
        populate_by_name = True

