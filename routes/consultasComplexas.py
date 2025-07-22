from enum import Enum
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta, timezone
from all_enum.status_enum import CategoriaProduto
from models.pedido_model import PedidoCreate, PedidoOut
from collections import defaultdict, Counter
from database import get_db
from database import pedidos_collection, produtos_collection, promocoes_collection, users_collection

from bson import ObjectId

router = APIRouter()

@router.get("/relatorios/vendas-por-categoria", tags=["Consultas complexas"])
async def vendas_por_categoria(
    categoria: CategoriaProduto | None = Query(default=None, description="Filtrar por categoria"),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    '''
    Retorna um relatório de vendas por categoria (Vestuário, Decoração, Eletrônicos e Brinquedos.

    Entidades acessadas: Pedido, Produto, Usuário
    '''
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

@router.get("/relatorios/gastos-usuarios-por-regiao", tags=["Consultas complexas"])
async def gastos_usuarios_por_regiao(
    cidade: Optional[str] = Query(None, description="Cidade do usuário (opcional)"),
    estado: Optional[str] = Query(None, description="Estado do usuário (opcional)"),
    periodo_dias: Optional[int] = Query(365, description="Número de dias para trás para considerar os pedidos (padrão: 365)"),
):
    '''
    Relatório de gastos dos usuários por região

    Entidades acessadas: Usuário, Pedido e Produto
    '''
    data_limite = datetime.utcnow() - timedelta(days=periodo_dias)

    match_usuarios: Dict[str, Any] = {}
    if cidade:
        match_usuarios["endereco_de_entrega.cidade"] = {"$regex": f"^{cidade}$", "$options": "i"}
    if estado:
        match_usuarios["endereco_de_entrega.estado"] = {"$regex": f"^{estado}$", "$options": "i"}

    pipeline: List[Dict[str, Any]] = [
        {
            "$match": {
                "data_pedido": {"$gte": data_limite}
            }
        },
        {
            "$unwind": "$itens"
        },
        {
            "$lookup": {
                "from": "produtos",
                "localField": "itens.id_produto",
                "foreignField": "_id",
                "as": "produtoInfo"
            }
        },
        {
            "$unwind": "$produtoInfo"
        },
        {
            "$lookup": {
                "from": "usuarios",
                "localField": "id_usuario",
                "foreignField": "_id",
                "as": "usuarioInfo"
            }
        },
        {
            "$unwind": "$usuarioInfo"
        },
    ]

    if match_usuarios:
        pipeline.append({
            "$match": {
                "usuarioInfo." + k: v for k, v in match_usuarios.items()
            }
        })

    pipeline.append({
        "$group": {
            "_id": "$usuarioInfo._id",
            "nome_usuario": {"$first": "$usuarioInfo.nome"},
            "email_usuario": {"$first": "$usuarioInfo.email"},
            "cidade_usuario": {"$first": "$usuarioInfo.endereco_de_entrega.cidade"},
            "estado_usuario": {"$first": "$usuarioInfo.endereco_de_entrega.estado"},
            "total_gasto": {
                "$sum": { "$multiply": ["$itens.quantidade", "$itens.preco_unitario"] }
            },
            "produtos_comprados": {
                "$push": {
                    "id": {"$toString": "$produtoInfo._id"}, 
                    "nome": "$produtoInfo.nome",
                    "quantidade_comprada": "$itens.quantidade"
                }
            }
        }
    })

    pipeline.append({
        "$addFields": {
            "produtos_comprados_consolidados": {
                "$reduce": {
                    "input": "$produtos_comprados",
                    "initialValue": [],
                    "in": {
                        "$let": {
                            "vars": {
                                "foundIndex": {
                                    "$indexOfArray": ["$$value.id", "$$this.id"]
                                }
                            },
                            "in": {
                                "$cond": [
                                    { "$ne": ["$$foundIndex", -1] },
                                    {
                                        "$map": {
                                            "input": "$$value",
                                            "as": "el",
                                            "in": {
                                                "$cond": [
                                                    { "$eq": ["$$el.id", "$$this.id"] },
                                                    {
                                                        "id": "$$el.id",
                                                        "nome": "$$el.nome",
                                                        "quantidade_comprada": { "$add": ["$$el.quantidade_comprada", "$$this.quantidade_comprada"] }
                                                    },
                                                    "$$el"
                                                ]
                                            }
                                        }
                                    },
                                    { "$concatArrays": ["$$value", [{ "id": "$$this.id", "nome": "$$this.nome", "quantidade_comprada": "$$this.quantidade_comprada" }]] }
                                ]
                            }
                        }
                    }
                }
            }
        }
    })

    pipeline.append({
        "$sort": {
            "total_gasto": -1
        }
    })

    pipeline.append({
        "$project": {
            "_id": 0,
            "usuario": {
                "id": {"$toString": "$_id"},
                "nome": "$nome_usuario",
                "email": "$email_usuario",
                "cidade": "$cidade_usuario",
                "estado": "$estado_usuario"
            },
            "total_gasto": "$total_gasto",
            "produtos_mais_comprados": "$produtos_comprados_consolidados"
        }
    })

    result = await pedidos_collection.aggregate(pipeline).to_list(length=None)

    if not result:
        raise HTTPException(status_code=404, detail="Nenhum gasto ou usuário encontrado com os critérios fornecidos.")

    return result

@router.get("/relatorios/promocoes-vendas-por-categoria-detalhado" , tags=["Consultas complexas"])
async def promocoes_vendas_por_categoria_detalhado():
    '''
    Gera um relatório de vendas de produtos em promoção.

    Entidades acessadas: Produto, Variação, Promocao e pedido.
    '''
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

@router.get("/relatorios/produtos-em-promocao", tags=["Consultas complexas"])
async def produtos_em_promocao(db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Gera uma lista de todos os produtos que estão atualmente em promoção,
    detalhando a promoção aplicada.
    
    Entidades acessadas: Produto, Promocao e Variacao.
    """
    agora = datetime.now(timezone.utc)
    resultado_final = []

    # 1. Encontrar todas as promoções ativas
    cursor_promocoes_ativas = db.promocoes.find({
        "data_inicio": {"$lte": agora},
        "data_fim": {"$gte": agora}
    })

    async for promocao in cursor_promocoes_ativas:
        ids_produtos_na_promo = promocao.get("produtos_aplicaveis", [])
        
        for id_produto_obj in ids_produtos_na_promo:
            # 2. Buscar os detalhes do produto
            produto = await db.produtos.find_one({"_id": id_produto_obj})
            if not produto:
                continue

            variacoes_com_desconto = []
            # 3. Buscar todas as variações daquele produto
            cursor_variacoes = db.variacoes_produto.find({"produto_id": produto["_id"]})
            
            async for variacao in cursor_variacoes:
                preco_base = produto.get("preco_base", 0)
                preco_adicional = variacao.get("preco_adicional", 0)
                preco_original = preco_base + preco_adicional

                # 4. Calcular o preço com desconto
                tipo_desconto = promocao.get("tipo_desconto")
                valor_desconto = promocao.get("valor_desconto", 0)
                preco_final = preco_original

                if tipo_desconto == "porcentagem":
                    preco_final = preco_original * (1 - valor_desconto / 100)
                elif tipo_desconto == "valor_fixo":
                    preco_final = preco_original - valor_desconto

                # Garantir que o preço não seja negativo
                preco_final = max(0, round(preco_final, 2))

                variacoes_com_desconto.append({
                    "sku": variacao.get("sku"),
                    "atributos": variacao.get("atributos"),
                    "estoque": variacao.get("estoque"),
                    "preco_original": round(preco_original, 2),
                    "preco_com_desconto": preco_final
                })
            
            # Adicionar o produto e suas variações promocionais ao resultado
            if variacoes_com_desconto:
                resultado_final.append({
                    "produto_id": str(produto["_id"]),
                    "nome_produto": produto.get("nome"),
                    "categoria": produto.get("categoria"),
                    "promocao": {
                        "nome": promocao.get("nome"),
                        "data_fim": promocao.get("data_fim"),
                        "tipo_desconto": promocao.get("tipo_desconto"),
                        "valor_desconto": promocao.get("valor_desconto")
                    },
                    "variacoes": variacoes_com_desconto
                })

    return resultado_final


@router.get("/relatorios/historico-usuario/{id_usuario}", tags=["Consultas complexas"])
async def historico_pedidos_usuario(id_usuario: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Recupera o histórico completo de pedidos para um usuário específico,
    enriquecendo cada item do pedido com detalhes do produto e da variação.

    Entidades acessadas: Usuario, Produto e pedido
    """
    # 1. Validar o ObjectId e verificar se o usuário existe
    if not ObjectId.is_valid(id_usuario):
        raise HTTPException(status_code=400, detail="Formato do ID de usuário inválido.")
    
    user_id_obj = ObjectId(id_usuario)
    usuario = await db.usuarios.find_one({"_id": user_id_obj})
    if not usuario:
        raise HTTPException(status_code=404, detail=f"Usuário com ID '{id_usuario}' não encontrado.")

    # 2. Buscar todos os pedidos do usuário
    cursor_pedidos = db.pedidos.find({"id_usuario": user_id_obj})
    
    historico_pedidos = []
    async for pedido in cursor_pedidos:
        itens_detalhados = []
        # 3. Iterar sobre os itens de cada pedido
        for item in pedido.get("itens", []):
            produto = None
            
            # 4. Buscar os detalhes do produto
            if item.get("id_produto"):
                produto = await db.produtos.find_one({"_id": item["id_produto"]})

            item_enriquecido = {
                "nome_produto": produto.get("nome") if produto else "Produto não encontrado",
                "marca": produto.get("marca") if produto else "N/A",
                "sku_selecionado": item.get("sku_selecionado"),
                "atributos_selecionados": item.get("atributos_selecionados", {}),
                "quantidade_comprada": item.get("quantidade"),
                "preco_unitario_pago": item.get("preco_unitario")
            }
            itens_detalhados.append(item_enriquecido)
        
        # 6. Reconstruir a estrutura do pedido com os itens detalhados
        pedido_completo = {
            "pedido_id": str(pedido["_id"]),
            "data_pedido": pedido.get("data_pedido"),
            "status": pedido.get("status"),
            "valor_total_pago": pedido.get("valor_total"),
            "forma_pagamento": pedido.get("forma_pagamento"),
            "itens": itens_detalhados
        }
        historico_pedidos.append(pedido_completo)

    return {
        "usuario": {
            "id": str(usuario["_id"]),
            "nome": usuario.get("nome"),
            "email": usuario.get("email"),
            "data_de_cadastro": usuario.get("data_de_cadastro")
        },
        "total_pedidos": len(historico_pedidos),
        "historico": historico_pedidos
    }


class OrdemRanking(str, Enum):
    receita = "receita"
    unidades = "unidades"

@router.get("/relatorios/ranking-produtos/best-sellers", tags=["Consultas complexas"])
async def ranking_best_sellers(
    ordem: OrdemRanking = Query(default=OrdemRanking.receita, description="Critério para ordenar o ranking: 'receita' ou 'unidades'"),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Cria uma lista ordenada dos produtos mais vendidos (best-sellers),
    calculando a receita total e o número de unidades vendidas para cada um.
    
    Entidades acessadas: Produtos, Variação, Pedido.
    """
    
    pipeline = [
        { "$match": { "status": "Entregue" } },
        { "$unwind": "$itens" },
        {
            "$group": {
                "_id": "$itens.id_produto",
                "total_unidades_vendidas": { "$sum": "$itens.quantidade" },
                "receita_gerada": { 
                    "$sum": { "$multiply": ["$itens.quantidade", "$itens.preco_unitario"] } 
                }
            }
        },
        {
            "$lookup": {
                "from": "produtos",
                "localField": "_id",
                "foreignField": "_id",
                "as": "detalhes_produto"
            }
        },
        { "$unwind": "$detalhes_produto" },

        # ESTÁGIO CORRIGIDO
        {
            "$project": {
                "_id": 0,
                "produto_id": { "$toString": "$_id" },  # <-- CORREÇÃO APLICADA AQUI
                "nome_produto": "$detalhes_produto.nome",
                "categoria": "$detalhes_produto.categoria",
                "marca": "$detalhes_produto.marca",
                "unidades_vendidas": "$total_unidades_vendidas",
                "receita_total": { "$round": ["$receita_gerada", 2] }
            }
        },
        
        # Estágio de ordenação
        {
            "$sort": {
                "receita_total" if ordem == OrdemRanking.receita else "unidades_vendidas": -1
            }
        }
    ]

    cursor = db.pedidos.aggregate(pipeline)
    ranking = await cursor.to_list(length=None)
    
    return ranking