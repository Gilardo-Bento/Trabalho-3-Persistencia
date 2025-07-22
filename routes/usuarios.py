from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from bson import ObjectId
from database import users_collection
from logger import get_logger
from models.usuario_model import UserCreate, UserOut
from pagination import PaginatedResponse, PaginationParams

logger = get_logger("usuarios_logger", "log/usuarios.log")

router = APIRouter(prefix="/usuarios", tags=["Usuários"])

@router.post("/create", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def criar_usuario(usuario: UserCreate):
    usuario_dict = usuario.model_dump()
    result = await users_collection.insert_one(usuario_dict)
    novo_usuario = await users_collection.find_one({"_id": result.inserted_id})
    
    logger.info(f"Usuário com id {result.inserted_id} criado.")
    return UserOut(**novo_usuario)

@router.get("/get_all", response_model=PaginatedResponse) 
async def listar_usuarios(pagination: PaginationParams = Depends()):
    total_items = await users_collection.count_documents({})

    skip = (pagination.page - 1) * pagination.per_page

    cursor = users_collection.find().skip(skip).limit(pagination.per_page)
    usuarios = [UserOut(**doc) async for doc in cursor]
    
    return PaginatedResponse(
        items=usuarios,
        total=total_items,
        page=pagination.page,
        per_page=pagination.per_page
    )

@router.get("/get_by_id/{usuario_id}", response_model=UserOut)
async def obter_usuario(usuario_id: str):
    if not ObjectId.is_valid(usuario_id):
        logger.warning(f"Id inválido o tentar acessar usuario")
        raise HTTPException(status_code=400, detail="ID inválido.")
    usuario = await users_collection.find_one({"_id": ObjectId(usuario_id)})
    if not usuario:
        logger.warning(f"Usuário não encontrado com o id {usuario_id}")
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    logger.warning(f"Usuário com id {usuario_id} retornado")
    return UserOut(**usuario)

@router.put("/update/{usuario_id}", response_model=UserOut)
async def atualizar_usuario(usuario_id: str, dados: UserCreate):
    if not ObjectId.is_valid(usuario_id):
        logger.warning(f"Id inválido o tentar atualizar usuario")
        raise HTTPException(status_code=400, detail="ID inválido.")
    result = await users_collection.update_one(
        {"_id": ObjectId(usuario_id)},
        {"$set": dados.model_dump()}
    )
    if result.matched_count == 0:
        logger.warning(f"Usuário não encontrado com o id {usuario_id}")
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    usuario = await users_collection.find_one({"_id": ObjectId(usuario_id)})

    logger.info(f"Usuário com id {usuario_id} atualizado.")
    return UserOut(**usuario)

@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_usuario(usuario_id: str):
    if not ObjectId.is_valid(usuario_id):
        logger.warning(f"Id inválido o tentar deletar usuario")
        raise HTTPException(status_code=400, detail="ID inválido.")
    result = await users_collection.delete_one({"_id": ObjectId(usuario_id)})
    if result.deleted_count == 0:
        logger.warning(f"Usuário não encontrado com o id {usuario_id}")
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    
    logger.info(f"Usuário com id {usuario_id} deletado.")
    return

@router.get("/filtros/", response_model=PaginatedResponse[UserOut])
async def pesquisar_usuarios(
    nome: Optional[str] = None,
    cidade: Optional[str] = None,
    estado: Optional[str] = None,
    data_inicio: Optional[datetime] = None,
    data_fim: Optional[datetime] = None,   
    ordenar_por: str = "nome",
    ordem: str = "asc",
    pagination: PaginationParams = Depends()
):
    filtros = {}

    # Construção dos filtros de texto
    if nome:
        filtros["nome"] = {"$regex": nome, "$options": "i"}
    if cidade:
        filtros["endereco_de_entrega.cidade"] = {"$regex": cidade, "$options": "i"}
    if estado:
        filtros["endereco_de_entrega.estado"] = {"$regex": estado, "$options": "i"}

    # Construção do filtro de intervalo de datas
    filtro_data = {}
    if data_inicio:
        filtro_data["$gte"] = data_inicio
    if data_fim:
        filtro_data["$lte"] = data_fim     
    
    if filtro_data:
        filtros["data_de_cadastro"] = filtro_data

    total_items = await users_collection.count_documents(filtros)
    sort_order = 1 if ordem.lower() == "asc" else -1
    skip = (pagination.page - 1) * pagination.per_page

    cursor = users_collection.find(filtros).sort(ordenar_por, sort_order).skip(skip).limit(pagination.per_page)
    usuarios = [UserOut(**doc) async for doc in cursor]

    return PaginatedResponse(
        items=usuarios,
        total=total_items,
        page=pagination.page,
        per_page=pagination.per_page
    )
    
    
    
@router.get("/quantidade", response_model=int)
async def contar_usuarios():
    total = await users_collection.count_documents({})
    logger.info(f"Total de usuários: {total}")
    return total