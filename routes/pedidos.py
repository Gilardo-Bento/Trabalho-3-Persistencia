from bson import ObjectId

from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Optional
from database import pedidos_collection
from models.pedido_model import PedidoCreate, PedidoOut, StatusPedido, FormaPagamento
from models.base import PyObjectId

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])

@router.post("/", response_model=PedidoOut, status_code=status.HTTP_201_CREATED)
async def criar_pedido(pedido: PedidoCreate):
    pedido_dict = pedido.model_dump(by_alias=True)
    result = await pedidos_collection.insert_one(pedido_dict)
    novo_pedido = await pedidos_collection.find_one({"_id": result.inserted_id})
    return PedidoOut(**novo_pedido)


@router.get("/", response_model=List[PedidoOut])
async def listar_pedidos(page: int = 1, limit: int = 10):
    skip = (page - 1) * limit
    cursor = pedidos_collection.find().skip(skip).limit(limit)
    pedidos = []
    async for doc in cursor:
        # Converte string de data para datetime objeto
        if isinstance(doc["data_pedido"], str):
            doc["data_pedido"] = datetime.fromisoformat(doc["data_pedido"])
        pedidos.append(PedidoOut(**doc))
    return pedidos


@router.get("/{pedido_id}", response_model=PedidoOut)
async def obter_pedido(pedido_id: str):
    if not ObjectId.is_valid(pedido_id):
        raise HTTPException(status_code=400, detail="ID inválido.")
    pedido = await pedidos_collection.find_one({"_id": ObjectId(pedido_id)})
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    return PedidoOut(**pedido)



@router.put("/{pedido_id}", response_model=PedidoOut)
async def atualizar_pedido(pedido_id: str, dados: PedidoCreate):
    if not ObjectId.is_valid(pedido_id):
        raise HTTPException(status_code=400, detail="ID inválido.")
    result = await pedidos_collection.update_one(
        {"_id": ObjectId(pedido_id)},
        {"$set": dados.model_dump()}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    pedido = await pedidos_collection.find_one({"_id": ObjectId(pedido_id)})
    return PedidoOut(**pedido)



@router.delete("/{pedido_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_pedido(pedido_id: str):
    if not ObjectId.is_valid(pedido_id):
        raise HTTPException(status_code=400, detail="ID inválido.")
    result = await pedidos_collection.delete_one({"_id": ObjectId(pedido_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    return



@router.get("/quantidade/total", response_model=dict)
async def contar_pedidos():
    total = await pedidos_collection.count_documents({})
    return {"total_pedidos": total}



@router.get("/filtro/", response_model=List[PedidoOut])
async def filtrar_pedidos(
    status: Optional[StatusPedido] = None,
    forma_pagamento: Optional[FormaPagamento] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None
):
    filtros = {}

    if status:
        filtros["status"] = status.value
    if forma_pagamento:
        filtros["forma_pagamento"] = forma_pagamento.value

    if data_inicio or data_fim:
        filtros["data_pedido"] = {}

        if data_inicio:
            try:
                dt_inicio = datetime.fromisoformat(data_inicio)
                filtros["data_pedido"]["$gte"] = dt_inicio
            except ValueError:
                raise HTTPException(status_code=400, detail="data_inicio inválida, use ISO format")
        if data_fim:
            try:
                dt_fim = datetime.fromisoformat(data_fim)
                filtros["data_pedido"]["$lte"] = dt_fim
            except ValueError:
                raise HTTPException(status_code=400, detail="data_fim inválida, use ISO format")

        if not filtros["data_pedido"]:
            filtros.pop("data_pedido")

    cursor = pedidos_collection.find(filtros)
    return [PedidoOut(**doc) async for doc in cursor]



@router.get("/filtro/por-usuario/", response_model=List[PedidoOut])
async def filtrar_pedidos_por_usuario(
    id_usuario: PyObjectId,
    page: int = 1,
    limit: int = 10
):
    skip = (page - 1) * limit
    cursor = pedidos_collection.find({"id_usuario": id_usuario}).skip(skip).limit(limit)
    return [PedidoOut(**doc) async for doc in cursor]




def calcular_intervalo(ano: int, mes: Optional[int] = None) -> tuple[datetime, datetime]:
    if mes:
        inicio = datetime(ano, mes, 1)
        fim = datetime(ano + 1, 1, 1) if mes == 12 else datetime(ano, mes + 1, 1)
    else:
        inicio = datetime(ano, 1, 1)
        fim = datetime(ano + 1, 1, 1)
    return inicio, fim

@router.get("/filtro/ano/{ano}", response_model=List[PedidoOut])
async def filtrar_pedidos_por_data(
    ano: int,
    mes: Optional[int] = Query(None, ge=1, le=12, description="Mês opcional para filtrar os pedidos")
):
    inicio, fim = calcular_intervalo(ano, mes)

    filtro = {
        "data_pedido": {"$gte": inicio, "$lt": fim}
    }

    cursor = pedidos_collection.find(filtro)

    pedidos = [PedidoOut(**doc) async for doc in cursor]
    return pedidos

@router.get("/ordenar/", response_model=List[PedidoOut])
async def ordenar_pedidos(
    campo: str = "data_pedido",  # campo para ordenar (ex: data_pedido, valor_total)
    ordem: str = "desc",         # "asc" ou "desc"
    page: int = 1,
    limit: int = 10
):
    sort_order = 1 if ordem.lower() == "asc" else -1
    skip = (page - 1) * limit
    cursor = pedidos_collection.find().sort(campo, sort_order).skip(skip).limit(limit)
    return [PedidoOut(**doc) async for doc in cursor]


@router.get("/buscar-produto/", response_model=List[PedidoOut])
async def buscar_pedidos_por_nome_produto(nome_produto: str):
    filtro = {
        "itens.nome_produto": {"$regex": nome_produto, "$options": "i"}
    }
    cursor = pedidos_collection.find(filtro)
    return [PedidoOut(**doc) async for doc in cursor]
