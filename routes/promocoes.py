



from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Optional
from database import promocoes_collection
from models.promocao_model import PromocaoCreate, PromocaoOut, TipoDesconto
from datetime import datetime
from bson import ObjectId

router = APIRouter(prefix="/promocoes", tags=["Promoções"])


def validar_object_id(id: str, nome: str = "ID") -> ObjectId:
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail=f"{nome} inválido.")
    return ObjectId(id)


@router.post("/", response_model=PromocaoOut, status_code=status.HTTP_201_CREATED)
async def criar_promocao(promocao: PromocaoCreate):
    dados = promocao.dict(by_alias=True)

    if dados["data_inicio"] >= dados["data_fim"]:
        raise HTTPException(400, detail="Data de início deve ser anterior à data de fim.")

    if promocao.tipo_desconto == TipoDesconto.PORCENTAGEM and not (0 <= promocao.valor_desconto <= 100):
        raise HTTPException(400, detail="Porcentagem de desconto deve estar entre 0 e 100.")

    dados["produtos_aplicaveis"] = [ObjectId(prod_id) for prod_id in dados["produtos_aplicaveis"]]

    resultado = await promocoes_collection.insert_one(dados)
    nova = await promocoes_collection.find_one({"_id": resultado.inserted_id})
    return PromocaoOut(**nova)


@router.get("/", response_model=List[PromocaoOut])
async def listar_promocoes(page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100)):
    skip = (page - 1) * limit
    cursor = promocoes_collection.find().skip(skip).limit(limit)
    return [PromocaoOut(**doc) async for doc in cursor]


@router.get("/{promocao_id}", response_model=PromocaoOut)
async def obter_promocao(promocao_id: str):
    oid = validar_object_id(promocao_id, "ID da promoção")
    promocao = await promocoes_collection.find_one({"_id": oid})
    if not promocao:
        raise HTTPException(404, detail="Promoção não encontrada.")
    return PromocaoOut(**promocao)


@router.put("/{promocao_id}", response_model=PromocaoOut)
async def atualizar_promocao(promocao_id: str, promocao: PromocaoCreate):
    oid = validar_object_id(promocao_id, "ID da promoção")
    dados = promocao.dict(by_alias=True)

    if dados["data_inicio"] >= dados["data_fim"]:
        raise HTTPException(400, detail="Data de início deve ser anterior à data de fim.")

    dados["produtos_aplicaveis"] = [ObjectId(prod_id) for prod_id in dados["produtos_aplicaveis"]]

    resultado = await promocoes_collection.update_one({"_id": oid}, {"$set": dados})
    if resultado.matched_count == 0:
        raise HTTPException(404, detail="Promoção não encontrada.")

    atualizada = await promocoes_collection.find_one({"_id": oid})
    return PromocaoOut(**atualizada)


@router.delete("/{promocao_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_promocao(promocao_id: str):
    oid = validar_object_id(promocao_id, "ID da promoção")
    resultado = await promocoes_collection.delete_one({"_id": oid})
    if resultado.deleted_count == 0:
        raise HTTPException(404, detail="Promoção não encontrada.")


@router.get("/quantidade/total", response_model=dict)
async def contar_promocoes():
    total = await promocoes_collection.count_documents({})
    return {"total_promocoes": total}


@router.get("/filtro/", response_model=List[PromocaoOut])
async def filtrar_promocoes(
    nome: Optional[str] = None,
    tipo_desconto: Optional[TipoDesconto] = None,
    status: Optional[str] = Query(
        None,
        regex="^(ativas|futuras|expiradas)$",
        description="Filtrar promoções por status: ativas, futuras ou expiradas"
    )
):
    filtros = {}

    if nome:
        filtros["nome"] = {"$regex": nome, "$options": "i"}
    if tipo_desconto:
        filtros["tipo_desconto"] = tipo_desconto.value

    now = datetime.utcnow()
    if status == "ativas":
        filtros["data_inicio"] = {"$lte": now}
        filtros["data_fim"] = {"$gte": now}
    elif status == "futuras":
        filtros["data_inicio"] = {"$gt": now}
    elif status == "expiradas":
        filtros["data_fim"] = {"$lt": now}

    cursor = promocoes_collection.find(filtros)
    return [PromocaoOut(**doc) async for doc in cursor]



@router.get("/produto/{produto_id}", response_model=List[PromocaoOut])
async def promocoes_para_produto(produto_id: str):
    oid = validar_object_id(produto_id, "ID do produto")
    now = datetime.utcnow()
    cursor = promocoes_collection.find({
        "produtos_aplicaveis": oid,
        "data_inicio": {"$lte": now},
        "data_fim": {"$gte": now}
    })
    resultados = [PromocaoOut(**doc) async for doc in cursor]

    if not resultados:
        raise HTTPException(404, detail="Nenhuma promoção ativa encontrada para este produto.")
    return resultados


@router.get("/ordenar/", response_model=List[PromocaoOut])
async def ordenar_promocoes(
    campo: str = "data_inicio",
    ordem: str = "asc",
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100)
):
    sort_order = 1 if ordem == "asc" else -1
    skip = (page - 1) * limit

    cursor = promocoes_collection.find().sort(campo, sort_order).skip(skip).limit(limit)
    return [PromocaoOut(**doc) async for doc in cursor]
