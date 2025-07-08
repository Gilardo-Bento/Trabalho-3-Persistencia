
from bson import ObjectId
from pydantic import BaseModel, Field, GetCoreSchemaHandler
from pydantic_core import core_schema

class PyObjectId(ObjectId):

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("ID inválido")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        # Validação simples usando a função validate acima
        return core_schema.no_info_plain_validator_function(cls.validate)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        # Define que o JSON deve ser string
        return {"type": "string"}