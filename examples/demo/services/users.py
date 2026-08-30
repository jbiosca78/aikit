from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
from aikit.core.service_contract import ServiceContract, MethodSchema


class User(BaseModel):
    id: int
    username: str
    last_access: datetime
    credits: int


class Service(ServiceContract):
    name = "users"
    description = "Gestión de usuarios: listado, accesos y créditos."

    _users: Dict[int, User] = {
        1: User(id=1, username="alice", last_access=datetime.utcnow() - timedelta(days=1), credits=40),
        2: User(id=2, username="bob", last_access=datetime.utcnow() - timedelta(hours=5), credits=10),
        3: User(id=3, username="carol", last_access=datetime.utcnow() - timedelta(hours=1), credits=100),
    }

    # Métodos disponibles para la IA
    def list_methods(self) -> List[MethodSchema]:
        return [
            MethodSchema(
                name="list_users",
                description="Devuelve un listado de todos los usuarios.",
                params_schema={},
                returns_schema={
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "username": {"type": "string"},
                            "last_access": {"type": "string"},
                            "credits": {"type": "integer"},
                        },
                    },
                },
            ),
            MethodSchema(
                name="last_active_user",
                description="Devuelve el usuario que ha accedido más recientemente.",
                params_schema={},
                returns_schema={
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "username": {"type": "string"},
                        "last_access": {"type": "string"},
                        "credits": {"type": "integer"},
                    }
                }
            ),
            MethodSchema(
                name="add_credits",
                description="Añade créditos a un usuario.",
                params_schema={
                    "user_id": {"type": "integer"},
                    "amount": {"type": "integer"},
                },
                returns_schema={
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "username": {"type": "string"},
                        "credits": {"type": "integer"},
                    }
                }
            ),
        ]

    # Métodos reales
    def list_users(self) -> List[Dict]:
        return [u.dict() for u in self._users.values()]

    def last_active_user(self) -> Optional[Dict]:
        if not self._users:
            return None
        user = max(self._users.values(), key=lambda u: u.last_access)
        return user.dict()

    def add_credits(self, user_id: int, amount: int) -> Optional[Dict]:
        if amount <= 0 or amount > 1000:
            return {"error": "amount debe estar entre 1 y 1000", "user_id": user_id, "amount": amount}
        user = self._users.get(user_id)
        if not user:
            return None
        user.credits += amount
        return user.dict()
