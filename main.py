


from fastapi import FastAPI
from routes import consultasComplexas, usuarios, produtos, pedidos, promocoes

app = FastAPI()

app.include_router(usuarios.router)
app.include_router(produtos.router)
app.include_router(pedidos.router)
app.include_router(promocoes.router)

app.include_router(consultasComplexas.router)



# from fastapi import FastAPI
# from routes import professores, alunos


# app = FastAPI()
# app.include_router(professores.router)
# app.include_router(alunos.router)