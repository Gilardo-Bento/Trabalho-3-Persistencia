import math
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Dict, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase
from logger import get_logger
from database import get_db, pedidos_collection, users_collection, produtos_collection, variacao_collection
from models.pedido_model import PedidoCreate, PedidoOut, StatusPedido, FormaPagamento
from pagination import PaginationParams, PaginatedResponse
from bson import ObjectId

logger = get_logger("pedidos_logger", "log/pedidos.log")

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])

def validar_object_id(id_str: str, nome_campo: str = "ID") -> ObjectId:
    if not ObjectId.is_valid(id_str):
        logger.warning(f"Tentativa de usar um {nome_campo} inválido: {id_str}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{nome_campo} inválido.")
    return ObjectId(id_str)

@router.post("/create/", response_model=PedidoOut, status_code=status.HTTP_201_CREATED)
async def criar_pedido(pedido_data: PedidoCreate, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Cria um novo pedido, aplicando descontos de promoções ativas no momento da compra.
    """
    logger.info(f"Tentativa de criar pedido para o usuário ID: {pedido_data.id_usuario}")

    uid = validar_object_id(pedido_data.id_usuario, "ID do Usuário")
    if not await users_collection.find_one({"_id": uid}):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Usuário com ID '{uid}' não encontrado.")

    pedido_para_salvar = {
        "id_usuario": uid,
        "data_pedido": datetime.now(),
        "status": pedido_data.status.value,
        "forma_pagamento": pedido_data.forma_pagamento.value,
        "itens": [],
        "valor_total": 0.0
    }
    subtotal = 0.0

    for item_recebido in pedido_data.itens:
        variacao = await variacao_collection.find_one({"sku": item_recebido.sku_selecionado})
        
        if not variacao:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"SKU '{item_recebido.sku_selecionado}' não encontrado.")
        if variacao.get("estoque", 0) < item_recebido.quantidade:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Estoque insuficiente para o SKU '{item_recebido.sku_selecionado}'. Estoque atual: {variacao.get('estoque', 0)}.")
        
        produto = await produtos_collection.find_one({"_id": variacao["produto_id"]})
        if not produto:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Produto pai para o SKU '{item_recebido.sku_selecionado}' não encontrado.")
        
   
        preco_unitario, _ = await calcular_preco_final(db, produto, variacao)
        
        subtotal += item_recebido.quantidade * preco_unitario
        
        item_para_salvar_no_db = {
            "id_produto": variacao["produto_id"],
            "nome_produto": produto.get("nome", "Nome não disponível"),
            "sku_selecionado": item_recebido.sku_selecionado,
            "atributos_selecionados": variacao.get("atributos", {}),
            "quantidade": item_recebido.quantidade,
            "preco_unitario": round(preco_unitario, 2)
        }
        pedido_para_salvar["itens"].append(item_para_salvar_no_db)

    pedido_para_salvar["valor_total"] = round(subtotal, 2)
    
    result = await pedidos_collection.insert_one(pedido_para_salvar)
    novo_pedido = await pedidos_collection.find_one({"_id": result.inserted_id})
    logger.info(f"Pedido ID '{result.inserted_id}' criado com sucesso.")
    
    # Abate o estoque
    for item in pedido_para_salvar["itens"]:
        await variacao_collection.update_one(
            {"sku": item["sku_selecionado"]},
            {"$inc": {"estoque": -item["quantidade"]}}
        )

    return PedidoOut(**novo_pedido)

@router.get("/get_by_id/{pedido_id}", response_model=PedidoOut)
async def obter_pedido(pedido_id: str):
    oid = validar_object_id(pedido_id, "ID do Pedido")
    pedido = await pedidos_collection.find_one({"_id": oid})
    if not pedido:
        logger.warning(f"Pedido com ID '{pedido_id}' não encontrado.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado.")
    return PedidoOut(**pedido)

@router.get("/get_all", response_model=PaginatedResponse[PedidoOut])
async def listar_todos_pedidos(pagination: PaginationParams = Depends()):
    logger.info(f"Listando todos os pedidos - Página: {pagination.page}, Limite: {pagination.per_page}")
    total_items = await pedidos_collection.count_documents({})
    skip = (pagination.page - 1) * pagination.per_page

    cursor = pedidos_collection.find({}).sort("data_pedido", -1).skip(skip).limit(pagination.per_page)
    pedidos = [PedidoOut(**doc) async for doc in cursor]
    total_pages = math.ceil(total_items / pagination.per_page) if total_items > 0 else 0

    return PaginatedResponse(items=pedidos, total=total_items, page=pagination.page, per_page=pagination.per_page, total_pages=total_pages)
@router.put("/update/{pedido_id}", response_model=PedidoOut)
async def atualizar_pedido(pedido_id: str, dados: PedidoCreate, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Atualiza os dados de um pedido (como status) usando o modelo PedidoCreate como base,
    mas protegendo a lista de itens para que não seja sobrescrita.
    """
    logger.info(f"Tentativa de atualizar pedido ID: {pedido_id}")
    oid = validar_object_id(pedido_id, "ID do Pedido")
        
    # Pega todos os dados enviados pelo cliente.
    update_data = dados.model_dump(exclude_unset=True)
    
    # --- A LINHA MAIS IMPORTANTE DA CORREÇÃO ---
    # Remove a chave 'itens' do dicionário de atualização.
    # Isso impede que a operação $set substitua o array de itens no banco.
    # O ", None" garante que não haverá erro se a chave 'itens' não for enviada.
    update_data.pop("itens", None)
    
    # Se, após remover os itens, não sobrar nada para atualizar, informa o cliente.
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum campo válido para atualização foi fornecido (ex: status, forma_pagamento)."
        )

    # Agora, o $set só vai atualizar os campos que restaram em update_data,
    # como 'status' ou 'forma_pagamento', deixando 'itens' intacto.
    resultado = await db.pedidos.update_one({"_id": oid}, {"$set": update_data})
    
    if resultado.matched_count == 0:
        logger.warning(f"Pedido com ID '{pedido_id}' não encontrado para atualizar.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado.")
    
    pedido_atualizado = await db.pedidos.find_one({"_id": oid})
    logger.info(f"Pedido ID '{pedido_id}' atualizado com sucesso.")
    return PedidoOut(**pedido_atualizado)

@router.delete("/delete/{pedido_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_pedido(pedido_id: str):
    logger.info(f"Tentativa de deletar pedido ID: {pedido_id}")
    oid = validar_object_id(pedido_id, "ID do Pedido")
    resultado = await pedidos_collection.delete_one({"_id": oid})
    if resultado.deleted_count == 0:
        logger.warning(f"Pedido com ID '{pedido_id}' não encontrado para deletar.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado.")
    logger.info(f"Pedido ID '{pedido_id}' deletado com sucesso.")
    return

@router.get("/filtro/", response_model=PaginatedResponse[PedidoOut])
async def pesquisar_pedidos(
    pagination: PaginationParams = Depends(),
    id_usuario: Optional[str] = None,
    status: Optional[StatusPedido] = None,
    forma_pagamento: Optional[FormaPagamento] = None,
    data_inicio: Optional[datetime] = None,
    data_fim: Optional[datetime] = None,
    nome_produto: Optional[str] = None,
    ordenar_por: str = "data_pedido",
    ordem: str = "desc"
):
    filtros = {}
    logger.info(f"Pesquisando pedidos com filtros: id_usuario='{id_usuario}', status='{status}', nome_produto='{nome_produto}'")

    if id_usuario:
        filtros["id_usuario"] = validar_object_id(id_usuario, "ID do Usuário")
    if status:
        filtros["status"] = status.value
    if forma_pagamento:
        filtros["forma_pagamento"] = forma_pagamento.value
    if nome_produto:
        filtros["itens.nome_produto"] = {"$regex": nome_produto, "$options": "i"}

    filtro_data = {}
    if data_inicio:
        filtro_data["$gte"] = data_inicio
    if data_fim:
        data_fim_ajustada = data_fim.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        filtro_data["$lt"] = data_fim_ajustada
    if filtro_data:
        filtros["data_pedido"] = filtro_data

    total_items = await pedidos_collection.count_documents(filtros)
    sort_order = 1 if ordem.lower() == "asc" else -1
    skip = (pagination.page - 1) * pagination.per_page

    cursor = pedidos_collection.find(filtros).sort(ordenar_por, sort_order).skip(skip).limit(pagination.per_page)
    pedidos = [PedidoOut(**doc) async for doc in cursor]
    total_pages = math.ceil(total_items / pagination.per_page) if total_items > 0 else 0
    
    logger.info(f"Pesquisa encontrou {total_items} pedidos.")
    return PaginatedResponse(items=pedidos, total=total_items, page=pagination.page, per_page=pagination.per_page, total_pages=total_pages)


@router.get("/quantidade", response_model=int)
async def contar_pedidos():
    total = await pedidos_collection.count_documents({})
    logger.info(f"Total de pedidos: {total}")
    return total

async def calcular_preco_final(
    db: AsyncIOMotorDatabase, 
    produto: Dict, 
    variacao: Dict
) -> Tuple[float, Optional[Dict]]:
  
    agora = datetime.now()
    preco_original = produto.get("preco_base", 0) + variacao.get("preco_adicional", 0)
    
    promocao_ativa = await db.promocoes.find_one({
        "data_inicio": {"$lte": agora},
        "data_fim": {"$gte": agora},
        "produtos_aplicaveis": produto["_id"] 
    })

    if not promocao_ativa:
        return round(preco_original, 2), None

    tipo_desconto = promocao_ativa.get("tipo_desconto")
    valor_desconto = promocao_ativa.get("valor_desconto", 0)
    preco_final = preco_original

    if tipo_desconto == "porcentagem":
        preco_final = preco_original * (1 - valor_desconto / 100)
    elif tipo_desconto == "valor_fixo":
        preco_final = preco_original - valor_desconto

    preco_final_seguro = max(0, round(preco_final, 2))
    
    info_promocao = {
        "id_promocao": promocao_ativa["_id"],
        "nome_promocao": promocao_ativa.get("nome")
    }

    return preco_final_seguro, info_promocao