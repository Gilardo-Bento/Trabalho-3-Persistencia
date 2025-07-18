from bson import ObjectId

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field
from models.base import PyObjectId



class EnderecoUsuario(BaseModel):
    rua: str
    numero: str
    complemento: Optional[str] = None
    bairro: str
    cidade: str
    estado: str
    cep: str 

class UserBase(BaseModel):
    nome: str
    email: EmailStr
    data_de_cadastro: datetime = Field(default_factory=datetime.now)

    telefone: str
    endereco_de_entrega: EnderecoUsuario

class UserCreate(UserBase):
    pass

class UserOut(UserBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    
    class Config:
        json_encoders = {ObjectId: str}
        populate_by_name = True
