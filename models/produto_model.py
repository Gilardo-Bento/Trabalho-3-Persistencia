
from datetime import datetime
from bson import ObjectId
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from all_enum.status_enum import CategoriaProduto
from models.base import PyObjectId


class VariacaoProduto(BaseModel):
    sku: str
    atributos: Dict[str, str]
    preco_adicional: float
    estoque: int
    urls_imagens: List[str]

class ProdutoBase(BaseModel):
    nome: str
    descricao: str
    preco_base: float
    categoria: CategoriaProduto
    variacoes: List[VariacaoProduto] = []
    data_de_cadastro: Optional[datetime] = None  # campo opcional

    

class ProdutoCreate(ProdutoBase):
    pass

class ProdutoOut(ProdutoBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")

    class Config:
        json_encoders = {ObjectId: str}
        populate_by_name = True

