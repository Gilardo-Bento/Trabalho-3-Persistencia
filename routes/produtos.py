import math
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from database import produtos_collection
from logger import get_logger
from models.produto_model import ProdutoCreate, ProdutoOut, CategoriaProduto
from pagination import PaginationParams, PaginatedResponse
from bson import ObjectId
from pagination import PaginatedResponse

logger = get_logger("produtos_logger", "log/produtos.log")

router = APIRouter(prefix="/produtos", tags=["Produtos"])

@router.post("/create", response_model=ProdutoOut, status_code=status.HTTP_201_CREATED)
async def criar_produto(produto: ProdutoCreate):
    produto_dict = produto.model_dump()
    if not produto_dict.get("data_de_cadastro"):
        produto_dict["data_de_cadastro"] = datetime.utcnow()
    
    result = await produtos_collection.insert_one(produto_dict)
    novo_produto = await produtos_collection.find_one({"_id": result.inserted_id})

    logger.info(f"Produto com id {result.inserted_id} criado.")
    return ProdutoOut(**novo_produto)

@router.get("/get_by_id/{produto_id}", response_model=ProdutoOut)
async def obter_produto(produto_id: str):
    if not ObjectId.is_valid(produto_id):
        logger.warning(f"Id inválido {produto_id}")
        raise HTTPException(status_code=400, detail="ID de produto inválido.")
    produto = await produtos_collection.find_one({"_id": ObjectId(produto_id)})
    if not produto:
        logger.warning(f"Produto não encontrado com o id {produto_id}")
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    
    logger.info(f"Produto com id {produto_id} retornado.")
    return ProdutoOut(**produto)

@router.get("/get_all", response_model=PaginatedResponse[ProdutoOut])
async def listar_todos_produtos(pagination: PaginationParams = Depends()):
    total_items = await produtos_collection.count_documents({})
    skip = (pagination.page - 1) * pagination.per_page

    cursor = produtos_collection.find().skip(skip).limit(pagination.per_page)
    produtos = [ProdutoOut(**doc) async for doc in cursor]
    
    total_pages = math.ceil(total_items / pagination.per_page) if total_items > 0 else 0

    return PaginatedResponse(
        items=produtos,
        total=total_items,
        page=pagination.page,
        per_page=pagination.per_page,
        total_pages=total_pages
    )

@router.put("/update/{produto_id}", response_model=ProdutoOut)
async def atualizar_produto(produto_id: str, dados: ProdutoCreate):
    if not ObjectId.is_valid(produto_id):
        logger.warning(f"Id inválido {produto_id}")
        raise HTTPException(status_code=400, detail="ID de produto inválido.")
    
    update_data = dados.model_dump(exclude_unset=True)
    result = await produtos_collection.update_one(
        {"_id": ObjectId(produto_id)},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        logger.warning(f"Produto não encontrado com o id {produto_id}")
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    
    produto_atualizado = await produtos_collection.find_one({"_id": ObjectId(produto_id)})
    
    logger.info(f"Produto com id {produto_id} atualizado.")
    return ProdutoOut(**produto_atualizado)

@router.delete("/delete/{produto_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_produto(produto_id: str):
    if not ObjectId.is_valid(produto_id):
        logger.warning(f"Id inválido {produto_id}")
        raise HTTPException(status_code=400, detail="ID de produto inválido.")
    result = await produtos_collection.delete_one({"_id": ObjectId(produto_id)})
    if result.deleted_count == 0:
        logger.warning(f"Produto não encontrado com o id {produto_id}")
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    
    logger.info(f"Produto com id {produto_id} deletado.")
    return

@router.get("/filtros/", response_model=PaginatedResponse[ProdutoOut])
async def pesquisar_produtos(
    nome: Optional[str] = None,
    categoria: Optional[CategoriaProduto] = None,
    preco_min: Optional[float] = None,
    preco_max: Optional[float] = None,
    data_inicio: Optional[datetime] = None,
    data_fim: Optional[datetime] = None,
    ordenar_por: str = "data_de_cadastro",
    ordem: str = "desc",
    pagination: PaginationParams = Depends()
):
    filtros = {}

    if nome:
        filtros["nome"] = {"$regex": nome, "$options": "i"}
    if categoria:
        filtros["categoria"] = categoria.value
    
    # Filtro de preço
    filtro_preco = {}
    if preco_min is not None:
        filtro_preco["$gte"] = preco_min
    if preco_max is not None:
        filtro_preco["$lte"] = preco_max
    if filtro_preco:
        filtros["preco_base"] = filtro_preco

    # Filtro de data
    filtro_data = {}
    if data_inicio:
        filtro_data["$gte"] = data_inicio
    if data_fim:
        data_fim_ajustada = data_fim.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        filtro_data["$lt"] = data_fim_ajustada
    if filtro_data:
        filtros["data_de_cadastro"] = filtro_data

    total_items = await produtos_collection.count_documents(filtros)
    sort_order = 1 if ordem.lower() == "asc" else -1
    skip = (pagination.page - 1) * pagination.per_page

    cursor = produtos_collection.find(filtros).sort(ordenar_por, sort_order).skip(skip).limit(pagination.per_page)
    produtos = [ProdutoOut(**doc) async for doc in cursor]

    total_pages = math.ceil(total_items / pagination.per_page) if total_items > 0 else 0

    return PaginatedResponse(
        items=produtos,
        total=total_items,
        page=pagination.page,
        per_page=pagination.per_page,
        total_pages=total_pages
    )
