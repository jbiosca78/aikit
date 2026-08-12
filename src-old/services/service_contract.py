# app/microservices/service_contract.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from pydantic import BaseModel

class MethodSchema(BaseModel):
    name: str
    description: str
    params_schema: Dict[str, Any]  # JSON Schema-like
    returns_schema: Dict[str, Any]

class ServiceContract(ABC):
    name: str
    description: str

    @abstractmethod
    def list_methods(self) -> List[MethodSchema]:
        ...

    def get_method(self, name: str):
        method = getattr(self, name, None)
        if method is None or name.startswith("_"):
            raise AttributeError(f"Método {name} no encontrado")
        return method
