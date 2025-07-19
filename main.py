from fastapi import FastAPI
from routes import consultasComplexas, usuarios, produtos, pedidos, promocoes, variacao_produto

app = FastAPI()

app.include_router(usuarios.router)
app.include_router(produtos.router)
app.include_router(variacao_produto.router)
app.include_router(promocoes.router)
app.include_router(pedidos.router)
app.include_router(consultasComplexas.router)