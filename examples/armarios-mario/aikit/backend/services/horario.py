"""Servicio de ejemplo: consultas sobre el horario de atención."""

import unicodedata
from typing import Any, Dict, List

from aikit.core.service_contract import MethodSchema, ServiceContract


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", str(texto or ""))
    texto = "".join(ch for ch in texto if unicodedata.category(ch) != "Mn")
    return texto.casefold().strip()


class Service(ServiceContract):
    name = "horario"
    description = "Horario de atención, apertura, cierre, sábados y pausa de comida de Armarios Mario."

    def list_methods(self) -> List[MethodSchema]:
        return [
            MethodSchema(
                name="horario_atencion",
                description="Devuelve el horario semanal, incluyendo apertura, cierre, sábados y pausa de comida al mediodía.",
                params_schema={},
                required_params=[],
                returns_schema={"type": "object", "additionalProperties": True},
            ),
            MethodSchema(
                name="horario_dia",
                description="Devuelve el horario de atención de un día concreto de la semana, indicando apertura y cierre.",
                params_schema={
                    "dia": {
                        "type": "string",
                        "description": "Día de la semana a consultar, por ejemplo 'lunes' o 'sábado'.",
                    }
                },
                required_params=["dia"],
                returns_schema={"type": "object", "additionalProperties": True},
            ),
        ]

    def horario_atencion(self) -> Dict[str, Any]:
        return {
            "lunes": {"manana": "10:00-14:00", "tarde": "17:00-20:30"},
            "martes": {"manana": "10:00-14:00", "tarde": "17:00-20:30"},
            "miercoles": {"manana": "10:00-14:00", "tarde": "17:00-20:30"},
            "jueves": {"manana": "10:00-14:00", "tarde": "17:00-20:30"},
            "viernes": {"manana": "10:00-14:00", "tarde": "17:00-20:30"},
            "sabado": {"manana": "10:00-14:00", "tarde": "cerrado"},
            "domingo": "cerrado",
            "pausa_comida": "14:00-17:00 de lunes a viernes",
            "cierre_general": "20:30 de lunes a viernes y 14:00 los sábados",
        }

    def horario_dia(self, dia: str) -> Dict[str, Any]:
        horarios = self.horario_atencion()
        clave = _normalizar(dia)
        aliases = {"sabados": "sabado", "domingos": "domingo"}
        clave = aliases.get(clave, clave)
        horario = horarios.get(clave)
        if horario is None:
            return {"encontrado": False, "dia": dia}
        return {"encontrado": True, "dia": clave, "horario": horario}
