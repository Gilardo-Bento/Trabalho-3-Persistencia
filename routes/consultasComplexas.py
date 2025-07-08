
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta
from models.pedido_model import PedidoCreate, PedidoOut
from collections import defaultdict, Counter
from database import get_db
from database import pedidos_collection, produtos_collection, promocoes_collection, users_collection

from bson import ObjectId

router = APIRouter()

@router.get("/relatorios/vendas-por-categoria", tags=["Consultas complexas"])
async def vendas_por_categoria(
    categoria: str | None = Query(default=None, description="Filtrar por categoria"),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    ultimo_mes = datetime.now() - timedelta(days=30)

    cursor_pedidos = db.pedidos.find({
        "data_pedido": {"$gte": ultimo_mes},
        "status": "Entregue"
    })

    vendas_categoria = {}

    async for pedido in cursor_pedidos:
        id_usuario = pedido.get("id_usuario")
        usuario = await db.usuarios.find_one({"_id": ObjectId(id_usuario)})
        dados_usuario = {
            "nome": usuario.get("nome", "Desconhecido"),
            "email": usuario.get("email", "sem@email.com"),
            "telefone": usuario.get("telefone", "Não informado")
        } if usuario else {"nome": "Desconhecido", "email": "N/A", "telefone": "N/A"}

        for item in pedido.get("itens", []):
            produto = await db.produtos.find_one({"_id": ObjectId(item["id_produto"])})
            if not produto:
                continue

            cat = produto.get("categoria", "Indefinido")
            if categoria and cat != categoria:
                continue

            if cat not in vendas_categoria:
                vendas_categoria[cat] = {
                    "quantidade": 0,
                    "valor_total": 0.0,
                    "pedidos": []
                }

            vendas_categoria[cat]["quantidade"] += item.get("quantidade", 0)
            vendas_categoria[cat]["valor_total"] += item.get("quantidade", 0) * item.get("preco_unitario", 0.0)

            vendas_categoria[cat]["pedidos"].append({
                "nome_produto": produto.get("nome"),
                "sku": item.get("sku_selecionado"),
                "quantidade": item.get("quantidade"),
                "preco_unitario": item.get("preco_unitario"),
                "usuario": dados_usuario
            })

    resultado = []
    for cat, dados in vendas_categoria.items():
        resultado.append({
            "categoria": cat,
            "quantidade_vendida": dados["quantidade"],
            "valor_vendido": dados["valor_total"],
            "pedidos": dados["pedidos"]
        })

    return resultado



#usuarios que mais gastaram em um ano, por região e categoria


@router.get("/gastos-usuarios-regiao-categoria", tags=["Consultas complexas"])
async def gastos_usuarios_por_regiao_categoria(
    cidade: str = Query(..., description="Cidade do usuário"),
    estado: str = Query(..., description="Estado do usuário"),
    categoria: str = Query(..., description="Categoria do produto"),
):
    um_ano_atras = datetime.utcnow() - timedelta(days=365)

    # Buscar usuários da região
    usuarios_cursor = users_collection.find({
        "endereco_de_entrega.cidade": {"$regex": f"^{cidade}$", "$options": "i"},
        "endereco_de_entrega.estado": {"$regex": f"^{estado}$", "$options": "i"}
    })

    usuarios_ids = [user["_id"] async for user in usuarios_cursor]

    if not usuarios_ids:
        raise HTTPException(status_code=404, detail="Nenhum usuário encontrado na região informada.")

    # Buscar pedidos no último ano desses usuários
    pedidos_cursor = pedidos_collection.find({
        "id_usuario": {"$in": usuarios_ids},
        "data_pedido": {"$gte": um_ano_atras}
    })

    gastos_por_usuario = {}
    produtos_comprados_por_usuario = {}

    async for pedido in pedidos_cursor:
        user_id = pedido.get("id_usuario")
        if not user_id:
            continue

        for item in pedido.get("itens", []):
            produto_id = item.get("id_produto")
            quantidade = item.get("quantidade", 0)
            preco_unitario = item.get("preco_unitario", 0)

            if not produto_id:
                continue

            # Buscar produto para verificar categoria
            produto = await produtos_collection.find_one({"_id": produto_id})
            if not produto or produto.get("categoria", "").lower() != categoria.lower():
                continue

            valor_total_item = preco_unitario * quantidade

            gastos_por_usuario[user_id] = gastos_por_usuario.get(user_id, 0) + valor_total_item

            if user_id not in produtos_comprados_por_usuario:
                produtos_comprados_por_usuario[user_id] = {}

            produtos_comprados_por_usuario[user_id][produto_id] = produtos_comprados_por_usuario[user_id].get(produto_id, 0) + quantidade

    if not gastos_por_usuario:
        raise HTTPException(status_code=404, detail="Nenhuma compra encontrada para a categoria e região informadas.")

    # Ordenar usuários por maior gasto
    usuarios_ordenados = sorted(gastos_por_usuario.items(), key=lambda x: x[1], reverse=True)

    resposta = []
    for user_id, total_gasto in usuarios_ordenados:
        usuario = await users_collection.find_one({"_id": user_id})
        if not usuario:
            continue

        produtos_detalhados = []
        for prod_id, qtde in produtos_comprados_por_usuario[user_id].items():
            prod = await produtos_collection.find_one({"_id": prod_id})
            if not prod:
                continue
            produtos_detalhados.append({
                "id": str(prod["_id"]),
                "nome": prod.get("nome"),
                "quantidade_comprada": qtde
            })

        resposta.append({
            "usuario": {
                "id": str(usuario["_id"]),
                "nome": usuario.get("nome"),
                "email": usuario.get("email"),
                "cidade": usuario.get("endereco_de_entrega", {}).get("cidade"),
                "estado": usuario.get("endereco_de_entrega", {}).get("estado"),
            },
            "total_gasto": total_gasto,
            "produtos_mais_comprados": produtos_detalhados
        })

    return resposta




@router.get("/relatorios/promocoes-vendas-por-categoria-detalhado" , tags=["Consultas complexas"])
async def promocoes_vendas_por_categoria_detalhado():
    ultimo_mes = datetime.utcnow() - timedelta(days=30)

    promocoes_cursor = promocoes_collection.find({
        "data_inicio": {"$lte": datetime.utcnow()},
        "data_fim": {"$gte": datetime.utcnow()}
    })
    promocoes_ativas = [promo async for promo in promocoes_cursor]

    if not promocoes_ativas:
        raise HTTPException(status_code=404, detail="Nenhuma promoção ativa encontrada.")

    resultado_final = []

    for promocao in promocoes_ativas:
        promo_id = promocao["_id"]
        produtos_ids = promocao.get("produtos_aplicaveis", [])

        if not produtos_ids:
            continue

        pedidos_cursor = pedidos_collection.find({
            "data_pedido": {"$gte": ultimo_mes},
            "itens.id_produto": {"$in": produtos_ids}
        })

        total_vendido = 0
        valor_total = 0.0
        produtos_json = []
        pedidos_json = []

        for pedido in await pedidos_cursor.to_list(None):
            pedido_info = {
                "id": str(pedido["_id"]),
                "id_usuario": str(pedido["id_usuario"]),
                "data_pedido": pedido["data_pedido"],
                "itens": [],
                "valor_total": pedido.get("valor_total", 0)
            }

            for item in pedido.get("itens", []):
                produto_id = item.get("id_produto")
                if produto_id not in produtos_ids:
                    continue

                produto = await produtos_collection.find_one({"_id": produto_id})
                if not produto:
                    continue

                total_vendido += item.get("quantidade", 0)
                valor_total += item.get("quantidade", 0) * item.get("preco_unitario", 0.0)

                produto_info = {
                    "id": str(produto["_id"]),
                    "nome": produto["nome"],
                    "categoria": produto.get("categoria", "Indefinida"),
                    "preco_base": produto.get("preco_base", 0.0)
                }

                item_info = {
                    "nome_produto": produto["nome"],
                    "sku": item.get("sku_selecionado"),
                    "quantidade": item.get("quantidade"),
                    "preco_unitario": item.get("preco_unitario")
                }

                produtos_json.append(produto_info)
                pedido_info["itens"].append(item_info)

            if pedido_info["itens"]:
                pedidos_json.append(pedido_info)

        if pedidos_json:
            resultado_final.append({
                "categoria": produto_info.get("categoria", "Indefinida"),
                "promocao": {
                    "id": str(promocao["_id"]),
                    "nome": promocao.get("nome"),
                    "tipo_desconto": promocao.get("tipo_desconto"),
                    "valor_desconto": promocao.get("valor_desconto"),
                    "data_inicio": promocao.get("data_inicio"),
                    "data_fim": promocao.get("data_fim")
                },
                "total_vendido": total_vendido,
                "valor_total": valor_total,
                "produtos": produtos_json,
                "pedidos": pedidos_json
            })

    return resultado_final

















