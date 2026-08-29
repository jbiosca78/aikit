"""Servicio de ejemplo: consultas sobre el catálogo de armarios (CSV)."""

import csv
import os
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.service_contract import ServiceContract, MethodSchema

DEFAULT_CSV = Path(__file__).resolve().parents[2] / "web" / "catalogo.csv"

INT_FIELDS = {
    "precio_eur",
    "ancho_cm",
    "alto_cm",
    "fondo_cm",
    "baldas",
    "peso_max_por_balda_kg",
    "peso_total_max_kg",
    "puertas",
    "montaje_min",
    "stock",
}
LIST_FIELDS = {"colores"}


def _normalize(text: Any) -> str:
    t = unicodedata.normalize("NFD", str(text or ""))
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    return t.casefold().strip()


class Service(ServiceContract):
    name = "catalogo"
    description = "Catálogo de armarios a medida: modelos, medidas, precios, colores y disponibilidad."

    def __init__(self) -> None:
        self._csv_path = Path(os.getenv("AIKIT_CATALOGO_CSV") or DEFAULT_CSV)
        self._rows: List[Dict[str, Any]] = []
        self._loaded_mtime: Optional[float] = None

    def list_methods(self) -> List[MethodSchema]:
        modelo_schema = {
            "type": "object",
            "additionalProperties": True,
        }
        return [
            MethodSchema(
                name="listar_modelos",
                description="Devuelve un resumen de todos los modelos del catálogo (id, nombre, precio y medidas).",
                params_schema={},
                required_params=[],
                returns_schema={"type": "array", "items": modelo_schema},
            ),
            MethodSchema(
                name="obtener_modelo",
                description="Devuelve todos los datos de un modelo concreto buscando por id (ej. 'modelo1') o por nombre.",
                params_schema={
                    "modelo": {
                        "type": "string",
                        "description": "Identificador o nombre del modelo (ej. 'modelo2' o 'FLEX 140').",
                    }
                },
                required_params=["modelo"],
                returns_schema=modelo_schema,
            ),
            MethodSchema(
                name="buscar_modelos",
                description=(
                    "Busca modelos filtrando por precio, medidas, color o texto libre. "
                    "Todos los parámetros son opcionales; sin filtros devuelve todo el catálogo."
                ),
                params_schema={
                    "texto": {
                        "type": "string",
                        "description": "Texto libre a buscar en cualquier campo (material, observaciones, etc.).",
                    },
                    "color": {"type": "string", "description": "Color deseado (ej. 'roble claro')."},
                    "precio_max": {"type": "number", "description": "Precio máximo en euros."},
                    "ancho_max_cm": {"type": "number", "description": "Ancho máximo disponible en cm."},
                    "alto_max_cm": {"type": "number", "description": "Alto máximo disponible en cm."},
                    "fondo_max_cm": {"type": "number", "description": "Fondo máximo disponible en cm."},
                    "solo_disponibles": {
                        "type": "boolean",
                        "description": "Si es true, devuelve solo modelos con stock mayor que cero.",
                    },
                },
                required_params=[],
                returns_schema={"type": "array", "items": modelo_schema},
            ),
            MethodSchema(
                name="comparar_modelos",
                description="Compara dos modelos campo a campo para explicar diferencias.",
                params_schema={
                    "modelo_a": {"type": "string", "description": "Primer modelo (id o nombre)."},
                    "modelo_b": {"type": "string", "description": "Segundo modelo (id o nombre)."},
                },
                required_params=["modelo_a", "modelo_b"],
                returns_schema={"type": "object", "additionalProperties": True},
            ),
            MethodSchema(
                name="consultar_disponibilidad",
                description="Devuelve stock, disponibilidad y plazo de envío de un modelo.",
                params_schema={
                    "modelo": {"type": "string", "description": "Identificador o nombre del modelo."}
                },
                required_params=["modelo"],
                returns_schema={"type": "object", "additionalProperties": True},
            ),
        ]

    # --- carga de datos -------------------------------------------------

    def _load(self) -> List[Dict[str, Any]]:
        try:
            mtime = self._csv_path.stat().st_mtime
        except OSError as exc:
            raise RuntimeError(f"No se puede leer el catálogo en {self._csv_path}: {exc}") from exc

        if self._loaded_mtime == mtime:
            return self._rows

        rows: List[Dict[str, Any]] = []
        with self._csv_path.open(newline="", encoding="utf-8") as fh:
            for raw in csv.DictReader(fh):
                rows.append(self._parse_row(raw))

        self._rows = rows
        self._loaded_mtime = mtime
        return self._rows

    def _parse_row(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        row: Dict[str, Any] = {}
        for key, value in raw.items():
            if key is None:
                continue
            value = (value or "").strip()
            if key in INT_FIELDS:
                row[key] = int(value) if value.lstrip("-").isdigit() else None
            elif key in LIST_FIELDS:
                row[key] = [v.strip() for v in value.split("|") if v.strip()]
            else:
                row[key] = value
        return row

    def _find(self, modelo: str) -> Optional[Dict[str, Any]]:
        q = _normalize(modelo)
        if not q:
            return None
        rows = self._load()
        for row in rows:
            if _normalize(row.get("modelo")) == q or _normalize(row.get("nombre")) == q:
                return row
        for row in rows:
            if q in _normalize(row.get("nombre")) or q in _normalize(row.get("modelo")):
                return row
        return None

    # --- métodos expuestos ----------------------------------------------

    def listar_modelos(self) -> List[Dict[str, Any]]:
        return [
            {
                "modelo": row.get("modelo"),
                "nombre": row.get("nombre"),
                "precio_eur": row.get("precio_eur"),
                "ancho_cm": row.get("ancho_cm"),
                "alto_cm": row.get("alto_cm"),
                "fondo_cm": row.get("fondo_cm"),
                "colores": row.get("colores"),
                "disponibilidad": row.get("disponibilidad"),
            }
            for row in self._load()
        ]

    def obtener_modelo(self, modelo: str) -> Dict[str, Any]:
        row = self._find(modelo)
        if row is None:
            return {"encontrado": False, "modelo": modelo}
        return {"encontrado": True, **row}

    def buscar_modelos(
        self,
        texto: str = "",
        color: str = "",
        precio_max: Optional[float] = None,
        ancho_max_cm: Optional[float] = None,
        alto_max_cm: Optional[float] = None,
        fondo_max_cm: Optional[float] = None,
        solo_disponibles: bool = False,
    ) -> List[Dict[str, Any]]:
        q_texto = _normalize(texto)
        q_color = _normalize(color)
        limites = [
            ("precio_eur", precio_max),
            ("ancho_cm", ancho_max_cm),
            ("alto_cm", alto_max_cm),
            ("fondo_cm", fondo_max_cm),
        ]

        results: List[Dict[str, Any]] = []
        for row in self._load():
            if q_color and not any(q_color in _normalize(c) for c in row.get("colores", [])):
                continue
            if any(
                limite is not None and (row.get(campo) is None or row[campo] > limite)
                for campo, limite in limites
            ):
                continue
            if solo_disponibles and not (row.get("stock") or 0) > 0:
                continue
            if q_texto and q_texto not in _normalize(" ".join(str(v) for v in row.values())):
                continue
            results.append(row)
        return results

    def comparar_modelos(self, modelo_a: str, modelo_b: str) -> Dict[str, Any]:
        a = self._find(modelo_a)
        b = self._find(modelo_b)
        if a is None or b is None:
            return {
                "encontrado": False,
                "modelo_a": modelo_a if a is None else a.get("modelo"),
                "modelo_b": modelo_b if b is None else b.get("modelo"),
            }

        diferencias = {
            campo: {"a": a.get(campo), "b": b.get(campo)}
            for campo in a
            if a.get(campo) != b.get(campo)
        }
        return {
            "encontrado": True,
            "a": a,
            "b": b,
            "diferencias": diferencias,
        }

    def consultar_disponibilidad(self, modelo: str) -> Dict[str, Any]:
        row = self._find(modelo)
        if row is None:
            return {"encontrado": False, "modelo": modelo}
        return {
            "encontrado": True,
            "modelo": row.get("modelo"),
            "nombre": row.get("nombre"),
            "stock": row.get("stock"),
            "disponibilidad": row.get("disponibilidad"),
            "envio_dias": row.get("envio_dias"),
        }
