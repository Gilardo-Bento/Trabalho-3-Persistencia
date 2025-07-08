from databases import Database
import motor.motor_asyncio
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = "ecommerce"

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]  # Corrigido aqui

users_collection = db["usuarios"]
produtos_collection = db["produtos"]
pedidos_collection = db["pedidos"]
promocoes_collection = db["promocoes"]
produto_promocao_collection = db["produto_promocao"]



def get_db() -> Database:
    return db