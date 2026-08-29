"""Logica de dominio del catalogo. Identica en ambas implementaciones."""

import csv
import os
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_CSV = Path(__file__).resolve().parent.parent / "web" / "catalogo.csv"

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

_rows: List[Dict[str, Any]] = []
_loaded_mtime: Optional[float] = None


def _normalize(text: Any) -> str:
    t = unicodedata.normalize("NFD", str(text or ""))
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    return t.casefold().strip()


def _csv_path() -> Path:
    return Path(os.getenv("AIKIT_CATALOGO_CSV") or DEFAULT_CSV)


def _parse_row(raw: Dict[str, Any]) -> Dict[str, Any]:
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


def _load() -> List[Dict[str, Any]]:
    global _rows, _loaded_mtime
    path = _csv_path()
    mtime = path.stat().st_mtime
    if _loaded_mtime == mtime:
        return _rows

    rows: List[Dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for raw in csv.DictReader(fh):
            rows.append(_parse_row(raw))

    _rows = rows
    _loaded_mtime = mtime
    return _rows


def _find(model: str) -> Optional[Dict[str, Any]]:
    q = _normalize(model)
    if not q:
        return None
    rows = _load()
    for row in rows:
        if _normalize(row.get("modelo")) == q or _normalize(row.get("nombre")) == q:
            return row
    for row in rows:
        if q in _normalize(row.get("nombre")) or q in _normalize(row.get("modelo")):
            return row
    return None


def list_models() -> List[Dict[str, Any]]:
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
        for row in _load()
    ]


def get_model(model: str) -> Dict[str, Any]:
    row = _find(model)
    if row is None:
        return {"encontrado": False, "modelo": model}
    return {"encontrado": True, **row}


def search_models(
    text: str = "",
    color: str = "",
    max_price: Optional[float] = None,
    max_width_cm: Optional[float] = None,
    max_height_cm: Optional[float] = None,
    max_depth_cm: Optional[float] = None,
    only_available: bool = False,
) -> List[Dict[str, Any]]:
    q_text = _normalize(text)
    q_color = _normalize(color)
    limits = [
        ("precio_eur", max_price),
        ("ancho_cm", max_width_cm),
        ("alto_cm", max_height_cm),
        ("fondo_cm", max_depth_cm),
    ]

    results: List[Dict[str, Any]] = []
    for row in _load():
        if q_color and not any(q_color in _normalize(c) for c in row.get("colores", [])):
            continue
        if any(
            limit is not None and (row.get(field) is None or row[field] > limit)
            for field, limit in limits
        ):
            continue
        if only_available and not (row.get("stock") or 0) > 0:
            continue
        if q_text and q_text not in _normalize(" ".join(str(v) for v in row.values())):
            continue
        results.append(row)
    return results


def compare_models(model_a: str, model_b: str) -> Dict[str, Any]:
    a = _find(model_a)
    b = _find(model_b)
    if a is None or b is None:
        return {
            "encontrado": False,
            "modelo_a": model_a if a is None else a.get("modelo"),
            "modelo_b": model_b if b is None else b.get("modelo"),
        }

    differences = {
        field: {"a": a.get(field), "b": b.get(field)}
        for field in a
        if a.get(field) != b.get(field)
    }
    return {"encontrado": True, "a": a, "b": b, "diferencias": differences}


def check_availability(model: str) -> Dict[str, Any]:
    row = _find(model)
    if row is None:
        return {"encontrado": False, "modelo": model}
    return {
        "encontrado": True,
        "modelo": row.get("modelo"),
        "nombre": row.get("nombre"),
        "stock": row.get("stock"),
        "disponibilidad": row.get("disponibilidad"),
        "envio_dias": row.get("envio_dias"),
    }
