# from fastapi import APIRouter, HTTPException, status
# from typing import List
# from bson import ObjectId

# from database import users_collection  # importa a collection correta
# from models.models import UserCreate, UserOut

# router = APIRouter(prefix="/usuarios", tags=["Usuários"])

# @router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
# async def criar_usuario(usuario: UserCreate):
#     usuario_dict = usuario.model_dump()
#     result = await users_collection.insert_one(usuario_dict)
#     novo_usuario = await users_collection.find_one({"_id": result.inserted_id})
#     return UserOut(**novo_usuario)

# @router.get("/", response_model=List[UserOut])
# async def listar_usuarios(skip: int = 0, limit: int = 10):
#     cursor = users_collection.find().skip(skip).limit(limit)
#     return [UserOut(**doc) async for doc in cursor]

# @router.get("/{usuario_id}", response_model=UserOut)
# async def obter_usuario(usuario_id: str):
#     if not ObjectId.is_valid(usuario_id):
#         raise HTTPException(status_code=400, detail="ID inválido.")
#     usuario = await users_collection.find_one({"_id": ObjectId(usuario_id)})
#     if not usuario:
#         raise HTTPException(status_code=404, detail="Usuário não encontrado.")
#     return UserOut(**usuario)

# @router.put("/{usuario_id}", response_model=UserOut)
# async def atualizar_usuario(usuario_id: str, dados: UserCreate):
#     if not ObjectId.is_valid(usuario_id):
#         raise HTTPException(status_code=400, detail="ID inválido.")
#     result = await users_collection.update_one(
#         {"_id": ObjectId(usuario_id)},
#         {"$set": dados.model_dump()}
#     )
#     if result.matched_count == 0:
#         raise HTTPException(status_code=404, detail="Usuário não encontrado.")
#     usuario = await users_collection.find_one({"_id": ObjectId(usuario_id)})
#     return UserOut(**usuario)

# @router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
# async def deletar_usuario(usuario_id: str):
#     if not ObjectId.is_valid(usuario_id):
#         raise HTTPException(status_code=400, detail="ID inválido.")
#     result = await users_collection.delete_one({"_id": ObjectId(usuario_id)})
#     if result.deleted_count == 0:
#         raise HTTPException(status_code=404, detail="Usuário não encontrado.")
#     return


from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Optional
from bson import ObjectId
from database import users_collection
from models.usuario_model import UserCreate, UserOut

router = APIRouter(prefix="/usuarios", tags=["Usuários"])

# ------------------------------
# F1 - Inserir uma entidade (Create)
# ------------------------------
@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def criar_usuario(usuario: UserCreate):
    usuario_dict = usuario.model_dump()
    result = await users_collection.insert_one(usuario_dict)
    novo_usuario = await users_collection.find_one({"_id": result.inserted_id})
    return UserOut(**novo_usuario)

# ------------------------------
# F2 + F5 - Listar todos com paginação
# ------------------------------
@router.get("/", response_model=List[UserOut])
async def listar_usuarios(page: int = 1, limit: int = 10):
    skip = (page - 1) * limit
    cursor = users_collection.find().skip(skip).limit(limit)
    return [UserOut(**doc) async for doc in cursor]

# ------------------------------
# F3 - Ler (Read) usuário por ID
# ------------------------------
@router.get("/{usuario_id}", response_model=UserOut)
async def obter_usuario(usuario_id: str):
    if not ObjectId.is_valid(usuario_id):
        raise HTTPException(status_code=400, detail="ID inválido.")
    usuario = await users_collection.find_one({"_id": ObjectId(usuario_id)})
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return UserOut(**usuario)

# ------------------------------
# F3 - Atualizar (Update) usuário
# ------------------------------
@router.put("/{usuario_id}", response_model=UserOut)
async def atualizar_usuario(usuario_id: str, dados: UserCreate):
    if not ObjectId.is_valid(usuario_id):
        raise HTTPException(status_code=400, detail="ID inválido.")
    result = await users_collection.update_one(
        {"_id": ObjectId(usuario_id)},
        {"$set": dados.model_dump()}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    usuario = await users_collection.find_one({"_id": ObjectId(usuario_id)})
    return UserOut(**usuario)

# ------------------------------
# F3 - Deletar (Delete) usuário
# ------------------------------
@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_usuario(usuario_id: str):
    if not ObjectId.is_valid(usuario_id):
        raise HTTPException(status_code=400, detail="ID inválido.")
    result = await users_collection.delete_one({"_id": ObjectId(usuario_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return

# ------------------------------
# F4 - Mostrar a quantidade total
# ------------------------------
@router.get("/quantidade/total", response_model=dict)
async def contar_usuarios():
    total = await users_collection.count_documents({})
    return {"total_usuarios": total}

# ------------------------------
# F6 - Filtro por nome, cidade, estado
# ------------------------------
@router.get("/filtro/", response_model=List[UserOut])
async def filtrar_usuarios(
    nome: Optional[str] = None,
    cidade: Optional[str] = None,
    estado: Optional[str] = None
):
    filtros = {}

    if nome:
        filtros["nome"] = {"$regex": nome, "$options": "i"}
    if cidade:
        filtros["endereco_de_entrega.cidade"] = {"$regex": cidade, "$options": "i"}
    if estado:
        filtros["endereco_de_entrega.estado"] = {"$regex": estado, "$options": "i"}

    cursor = users_collection.find(filtros)
    return [UserOut(**doc) async for doc in cursor]



@router.get("/filtro/data", response_model=List[UserOut])
async def filtrar_por_ano(ano: Optional[int] = None):
    filtros = {}
    if ano:
        filtros["data_de_cadastro"] = {
            "$gte": datetime(ano, 1, 1),
            "$lt": datetime(ano + 1, 1, 1)
        }
    cursor = users_collection.find(filtros)
    return [UserOut(**doc) async for doc in cursor]



@router.get("/ordenar/", response_model=List[UserOut])
async def ordenar_usuarios(
    campo: str = "nome",
    ordem: str = "asc",
    page: int = 1,
    limit: int = 10
):
    sort_order = 1 if ordem.lower() == "asc" else -1
    skip = (page - 1) * limit
    cursor = users_collection.find().sort(campo, sort_order).skip(skip).limit(limit)
    return [UserOut(**doc) async for doc in cursor]
