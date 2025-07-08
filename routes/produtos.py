from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Optional
from database import produtos_collection
from models.produto_model import ProdutoCreate, ProdutoOut, CategoriaProduto
from models.base import PyObjectId
from bson import ObjectId

router = APIRouter(prefix="/produtos", tags=["Produtos"])

# ------------------------------
# F1 - Inserir uma entidade (Create)
# ------------------------------
@router.post("/", response_model=ProdutoOut, status_code=status.HTTP_201_CREATED)
async def criar_produto(produto: ProdutoCreate):
    produto_dict = produto.model_dump()
    if "data_de_cadastro" not in produto_dict or produto_dict["data_de_cadastro"] is None:
        produto_dict["data_de_cadastro"] = datetime.utcnow()
    result = await produtos_collection.insert_one(produto_dict)
    novo_produto = await produtos_collection.find_one({"_id": result.inserted_id})
    return ProdutoOut(**novo_produto)

# ------------------------------
# F2 + F5 - Listar todos com paginação
# ------------------------------
@router.get("/", response_model=List[ProdutoOut])
async def listar_produtos(page: int = 1, limit: int = 10):
    skip = (page - 1) * limit
    cursor = produtos_collection.find().skip(skip).limit(limit)
    return [ProdutoOut(**doc) async for doc in cursor]

# ------------------------------
# F3 - Ler (Read) produto por ID
# ------------------------------
@router.get("/{produto_id}", response_model=ProdutoOut)
async def obter_produto(produto_id: str):
    if not ObjectId.is_valid(produto_id):
        raise HTTPException(status_code=400, detail="ID inválido.")
    produto = await produtos_collection.find_one({"_id": ObjectId(produto_id)})
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    return ProdutoOut(**produto)

# ------------------------------
# F3 - Atualizar (Update) produto
# ------------------------------
@router.put("/{produto_id}", response_model=ProdutoOut)
async def atualizar_produto(produto_id: str, dados: ProdutoCreate):
    if not ObjectId.is_valid(produto_id):
        raise HTTPException(status_code=400, detail="ID inválido.")
    result = await produtos_collection.update_one(
        {"_id": ObjectId(produto_id)},
        {"$set": dados.model_dump()}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    produto = await produtos_collection.find_one({"_id": ObjectId(produto_id)})
    return ProdutoOut(**produto)

# ------------------------------
# F3 - Deletar (Delete) produto
# ------------------------------
@router.delete("/{produto_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_produto(produto_id: str):
    if not ObjectId.is_valid(produto_id):
        raise HTTPException(status_code=400, detail="ID inválido.")
    result = await produtos_collection.delete_one({"_id": ObjectId(produto_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    return

# ------------------------------
# F4 - Mostrar a quantidade total
# ------------------------------
@router.get("/quantidade/total", response_model=dict)
async def contar_produtos():
    total = await produtos_collection.count_documents({})
    return {"total_produtos": total}

# ------------------------------
# F6 - Filtro por nome, categoria e faixa de preço
# ------------------------------
@router.get("/filtro/", response_model=List[ProdutoOut])
async def filtrar_produtos(
    nome: Optional[str] = None,
    categoria: Optional[CategoriaProduto] = None,
    preco_min: Optional[float] = None,
    preco_max: Optional[float] = None
):
    filtros = {}

    if nome:
        filtros["nome"] = {"$regex": nome, "$options": "i"}
    if categoria:
        filtros["categoria"] = categoria.value
    if preco_min is not None or preco_max is not None:
        filtros["preco_base"] = {}
        if preco_min is not None:
            filtros["preco_base"]["$gte"] = preco_min
        if preco_max is not None:
            filtros["preco_base"]["$lte"] = preco_max
        if not filtros["preco_base"]:  # Caso fique vazio, remove
            filtros.pop("preco_base")

    cursor = produtos_collection.find(filtros)
    return [ProdutoOut(**doc) async for doc in cursor]



@router.get("/filtro/data", response_model=List[ProdutoOut])
async def filtrar_por_ano(ano: Optional[int] = None):
    filtros = {}
    if ano:
        filtros["data_de_cadastro"] = {
            "$gte": datetime(ano, 1, 1),
            "$lt": datetime(ano + 1, 1, 1)
        }
    cursor = produtos_collection.find(filtros)
    return [ProdutoOut(**doc) async for doc in cursor]

# ------------------------------
# Ordenar produtos por campo e ordem (asc/desc)
# ------------------------------
@router.get("/ordenar/", response_model=List[ProdutoOut])
async def ordenar_produtos(
    campo: str = "data_de_cadastro",
    ordem: str = "desc",
    page: int = 1,
    limit: int = 10
):
    sort_order = 1 if ordem.lower() == "asc" else -1
    skip = (page - 1) * limit

    cursor = produtos_collection.find().sort(campo, sort_order).skip(skip).limit(limit)
    return [ProdutoOut(**doc) async for doc in cursor]