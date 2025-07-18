


from fastapi import APIRouter, HTTPException
from typing import List
from bson import ObjectId
from logger import get_logger
from models.variacao_produto import VariacaoCreate, VariacaoOut
from database import variacao_collection, produtos_collection


router = APIRouter(prefix="", tags=["Variações de Produto"])

# Logger
logger = get_logger("variacoes_logger", "log/variacoes.log")


@router.post("/variacoes", response_model=VariacaoOut)
async def criar_variacao(variacao: VariacaoCreate):
    logger.info("Iniciando criação da variação: %s", variacao.model_dump())
    
    produto = await produtos_collection.find_one({"_id": variacao.produto_id})
    if not produto:
        logger.warning("Produto não encontrado para ID: %s", variacao.produto_id)
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    result = await variacao_collection.insert_one(variacao.dict())
    nova_variacao = await variacao_collection.find_one({"_id": result.inserted_id})
    
    logger.info("Variação criada com sucesso: %s", nova_variacao)
    return nova_variacao
# @router.post("/variacoes", response_model=VariacaoOut)
# async def criar_variacao(variacao: VariacaoCreate):
#     logger.info("Tentando criar variação para produto %s", variacao.produto_id)

#     produto = await produtos_collection.find_one({"_id": variacao.produto_id})
#     if not produto:
#         logger.warning("Produto não encontrado para ID: %s", variacao.produto_id)

#         raise HTTPException(status_code=404, detail="Produto não encontrado")
#     result = await variacao_collection.insert_one(variacao.dict())
#     nova_variacao = await variacao_collection.find_one({"_id": result.inserted_id})
    
#     logger.info("Variação criada com ID: %s", result.inserted_id)

#     return nova_variacao

@router.get("/produtos/{produto_id}/variacoes", response_model=List[VariacaoOut])
async def listar_variacoes(produto_id: str):
    if not ObjectId.is_valid(produto_id):
        raise HTTPException(status_code=400, detail="ID de produto inválido")
    variacoes_cursor = variacao_collection.find({"produto_id": ObjectId(produto_id)})
    return await variacoes_cursor.to_list(length=100)
