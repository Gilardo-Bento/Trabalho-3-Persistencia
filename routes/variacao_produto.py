import math
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from logger import get_logger
from models.variacao_produto import VariacaoCreate, VariacaoOut
from pagination import PaginationParams, PaginatedResponse
from database import produtos_collection, variacao_collection
from bson import ObjectId

logger = get_logger("variacoes_logger", "log/variacoes.log")

router = APIRouter(prefix="/variacoes", tags=["Variações de Produto"])

@router.post("/create", response_model=VariacaoOut, status_code=status.HTTP_201_CREATED)
async def criar_variacao(variacao: VariacaoCreate):
    logger.info(f"Tentativa de criar variação com SKU: {variacao.sku}")
    
    # 1. Verifica se o produto-pai existe
    produto_pai = await produtos_collection.find_one({"_id": variacao.produto_id})
    if not produto_pai:
        logger.warning(f"Falha ao criar variação: Produto com ID '{variacao.produto_id}' não encontrado.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produto com ID '{variacao.produto_id}' não encontrado."
        )

    # 2. Verifica se o SKU já existe
    variacao_existente = await variacao_collection.find_one({"sku": variacao.sku})
    if variacao_existente:
        logger.warning(f"Falha ao criar variação: SKU '{variacao.sku}' já está em uso.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"SKU '{variacao.sku}' já está em uso."
        )

    # 3. Insere a nova variação
    variacao_dict = variacao.model_dump()
    result = await variacao_collection.insert_one(variacao_dict)
    nova_variacao = await variacao_collection.find_one({"_id": result.inserted_id})
    
    logger.info(f"Variação com SKU '{nova_variacao['sku']}' criada com sucesso (ID: {result.inserted_id}).")
    return VariacaoOut(**nova_variacao)

@router.get("/get_all", response_model=PaginatedResponse[VariacaoOut])
async def listar_todas_variacoes(pagination: PaginationParams = Depends()):
    logger.info(f"Listando todas as variações - Página: {pagination.page}, Limite: {pagination.per_page}")
    
    total_items = await variacao_collection.count_documents({})
    skip = (pagination.page - 1) * pagination.per_page

    cursor = variacao_collection.find({}).sort("sku", 1).skip(skip).limit(pagination.per_page)
    variacoes = [VariacaoOut(**doc) async for doc in cursor]

    total_pages = math.ceil(total_items / pagination.per_page) if total_items > 0 else 0

    return PaginatedResponse(
        items=variacoes,
        total=total_items,
        page=pagination.page,
        per_page=pagination.per_page,
        total_pages=total_pages
    )

@router.get("/get_by_id/{variacao_id}", response_model=VariacaoOut)
async def obter_variacao(variacao_id: str):
    if not ObjectId.is_valid(variacao_id):
        logger.warning(f"Tentativa de obter variação com ID inválido: {variacao_id}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID de variação inválido.")
    
    variacao = await variacao_collection.find_one({"_id": ObjectId(variacao_id)})
    if not variacao:
        logger.warning(f"Variação com ID '{variacao_id}' não encontrada.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variação não encontrada.")
    
    return VariacaoOut(**variacao)

@router.put("/update/{variacao_id}", response_model=VariacaoOut)
async def atualizar_variacao(variacao_id: str, dados: VariacaoCreate):
    if not ObjectId.is_valid(variacao_id):
        logger.warning(f"Tentativa de atualizar variação com ID inválido: {variacao_id}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID de variação inválido.")
    
    update_data = dados.model_dump(exclude_unset=True)
    result = await variacao_collection.update_one(
        {"_id": ObjectId(variacao_id)},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        logger.warning(f"Variação com ID '{variacao_id}' não encontrada para atualizar.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variação não encontrada para atualizar.")
    
    variacao_atualizada = await variacao_collection.find_one({"_id": ObjectId(variacao_id)})
    logger.info(f"Variação ID '{variacao_id}' atualizada com sucesso.")
    return VariacaoOut(**variacao_atualizada)


@router.delete("/delete/{variacao_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_variacao(variacao_id: str):
    if not ObjectId.is_valid(variacao_id):
        logger.warning(f"Tentativa de deletar variação com ID inválido: {variacao_id}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID de variação inválido.")
    
    result = await variacao_collection.delete_one({"_id": ObjectId(variacao_id)})
    if result.deleted_count == 0:
        logger.warning(f"Variação com ID '{variacao_id}' não encontrada para deletar.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variação não encontrada para deletar.")
    
    logger.info(f"Variação ID '{variacao_id}' deletada com sucesso.")
    return

@router.get("/get_by_produto/{produto_id}", response_model=List[VariacaoOut])
async def listar_variacoes_por_produto(produto_id: str):
    if not ObjectId.is_valid(produto_id):
        logger.warning(f"Tentativa de listar variações com ID de produto inválido: {produto_id}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID de produto inválido.")
    
    cursor = variacao_collection.find({"produto_id": ObjectId(produto_id)})
    variacoes = [VariacaoOut(**doc) async for doc in cursor]
    logger.info(f"Encontradas {len(variacoes)} variações para o produto ID: {produto_id}")
    return variacoes


@router.get("/quantidade", response_model=int)
async def contar_variacoes():
    total = await variacao_collection.count_documents({})
    logger.info(f"Total de variações: {total}")
    return total