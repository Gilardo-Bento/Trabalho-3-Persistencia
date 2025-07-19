import math
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from logger import get_logger
from database import promocoes_collection
from models.promocao_model import PromocaoCreate, PromocaoOut, TipoDesconto
from pagination import PaginationParams, PaginatedResponse
from bson import ObjectId

logger = get_logger("promocoes_logger", "log/promocoes.log")

router = APIRouter(prefix="/promocoes", tags=["Promoções"])

def validar_object_id(id_str: str, nome_campo: str = "ID") -> ObjectId:
    if not ObjectId.is_valid(id_str):
        logger.warning(f"Tentativa de usar um {nome_campo} inválido: {id_str}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{nome_campo} inválido.")
    return ObjectId(id_str)

@router.post("/create", response_model=PromocaoOut, status_code=status.HTTP_201_CREATED)
async def criar_promocao(promocao: PromocaoCreate):
    logger.info(f"Tentativa de criar promoção: {promocao.nome}")
    dados = promocao.model_dump()

    if dados["data_inicio"] >= dados["data_fim"]:
        logger.warning(f"Falha ao criar promoção '{promocao.nome}': data de início posterior ou igual à data de fim.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Data de início deve ser anterior à data de fim.")

    if promocao.tipo_desconto == TipoDesconto.PORCENTAGEM and not (0 < promocao.valor_desconto <= 100):
        logger.warning(f"Falha ao criar promoção '{promocao.nome}': valor de porcentagem inválido ({promocao.valor_desconto}).")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Porcentagem de desconto deve estar entre 1 e 100.")

    dados["produtos_aplicaveis"] = [validar_object_id(pid, "ID do Produto") for pid in dados["produtos_aplicaveis"]]

    resultado = await promocoes_collection.insert_one(dados)
    nova_promocao = await promocoes_collection.find_one({"_id": resultado.inserted_id})
    
    logger.info(f"Promoção '{nova_promocao['nome']}' criada com sucesso (ID: {resultado.inserted_id}).")
    return PromocaoOut(**nova_promocao)

@router.get("/get_by_id/{promocao_id}", response_model=PromocaoOut)
async def obter_promocao(promocao_id: str):
    oid = validar_object_id(promocao_id, "ID da promoção")
    promocao = await promocoes_collection.find_one({"_id": oid})
    if not promocao:
        logger.warning(f"Promoção com ID '{promocao_id}' não encontrada.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promoção não encontrada.")
    return PromocaoOut(**promocao)

@router.get("/get_all", response_model=PaginatedResponse[PromocaoOut])
async def listar_todas_promocoes(pagination: PaginationParams = Depends()):
    logger.info(f"Listando todas as promoções - Página: {pagination.page}, Limite: {pagination.per_page}")
    total_items = await promocoes_collection.count_documents({})
    skip = (pagination.page - 1) * pagination.per_page

    cursor = promocoes_collection.find({}).sort("data_fim", -1).skip(skip).limit(pagination.per_page)
    promocoes = [PromocaoOut(**doc) async for doc in cursor]
    total_pages = math.ceil(total_items / pagination.per_page) if total_items > 0 else 0

    return PaginatedResponse(items=promocoes, total=total_items, page=pagination.page, per_page=pagination.per_page, total_pages=total_pages)

@router.put("/update/{promocao_id}", response_model=PromocaoOut)
async def atualizar_promocao(promocao_id: str, promocao_update: PromocaoCreate):
    logger.info(f"Tentativa de atualizar promoção ID: {promocao_id}")
    oid = validar_object_id(promocao_id, "ID da promoção")
    dados = promocao_update.model_dump(exclude_unset=True)

    resultado = await promocoes_collection.update_one({"_id": oid}, {"$set": dados})
    if resultado.matched_count == 0:
        logger.warning(f"Promoção com ID '{promocao_id}' não encontrada para atualizar.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promoção não encontrada.")

    promocao_atualizada = await promocoes_collection.find_one({"_id": oid})
    logger.info(f"Promoção ID '{promocao_id}' atualizada com sucesso.")
    return PromocaoOut(**promocao_atualizada)

@router.delete("/delete/{promocao_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_promocao(promocao_id: str):
    logger.info(f"Tentativa de deletar promoção ID: {promocao_id}")
    oid = validar_object_id(promocao_id, "ID da promoção")
    resultado = await promocoes_collection.delete_one({"_id": oid})
    if resultado.deleted_count == 0:
        logger.warning(f"Promoção com ID '{promocao_id}' não encontrada para deletar.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promoção não encontrada.")
    logger.info(f"Promoção ID '{promocao_id}' deletada com sucesso.")
    return

@router.get("/filtro/", response_model=PaginatedResponse[PromocaoOut])
async def pesquisar_promocoes(
    pagination: PaginationParams = Depends(),
    nome: Optional[str] = None,
    tipo_desconto: Optional[TipoDesconto] = None,
    produto_id: Optional[str] = None,
    status: Optional[str] = Query(None, description="Filtrar por 'ativas', 'futuras' ou 'expiradas'", regex="^(ativas|futuras|expiradas)$"),
    ordenar_por: str = "data_fim",
    ordem: str = "desc"
):
    filtros = {}
    now = datetime.utcnow()
    logger.info(f"Pesquisando promoções com filtros: nome='{nome}', tipo='{tipo_desconto}', status='{status}', produto_id='{produto_id}'")

    if nome:
        filtros["nome"] = {"$regex": nome, "$options": "i"}
    if tipo_desconto:
        filtros["tipo_desconto"] = tipo_desconto.value
    if produto_id:
        filtros["produtos_aplicaveis"] = validar_object_id(produto_id, "ID do Produto")
    
    if status == "ativas":
        filtros["data_inicio"] = {"$lte": now}
        filtros["data_fim"] = {"$gte": now}
    elif status == "futuras":
        filtros["data_inicio"] = {"$gt": now}
    elif status == "expiradas":
        filtros["data_fim"] = {"$lt": now}

    total_items = await promocoes_collection.count_documents(filtros)
    sort_order = 1 if ordem.lower() == "asc" else -1
    skip = (pagination.page - 1) * pagination.per_page

    cursor = promocoes_collection.find(filtros).sort(ordenar_por, sort_order).skip(skip).limit(pagination.per_page)
    promocoes = [PromocaoOut(**doc) async for doc in cursor]
    total_pages = math.ceil(total_items / pagination.per_page) if total_items > 0 else 0
    
    logger.info(f"Pesquisa encontrou {total_items} promoções.")
    return PaginatedResponse(items=promocoes, total=total_items, page=pagination.page, per_page=pagination.per_page, total_pages=total_pages)
