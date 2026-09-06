#!/usr/bin/env python3
"""Genera un informe reproducible del codigo de integracion por variante."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import platform
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path


SOURCE_EXTENSIONS = {".css", ".html", ".js", ".py", ".sh", ".yaml", ".yml"}
VARIANTS = ("bedrock", "langchain", "aikit")
WIDGET_FILES = ("chat-popup.js", "chat-popup.css")


def code_lines(path: Path) -> list[str]:
    lines: list[str] = []
    in_html_comment = False
    in_block_comment = False

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if path.suffix == ".html":
            if "<!--" in line:
                in_html_comment = "-->" not in line.split("<!--", 1)[1]
                line = line.split("<!--", 1)[0].strip()
            elif in_html_comment:
                in_html_comment = "-->" not in line
                continue
            if not line:
                continue

        if path.suffix in {".css", ".js"}:
            if in_block_comment:
                if "*/" not in line:
                    continue
                in_block_comment = False
                line = line.split("*/", 1)[1].strip()
            if line.startswith("/*"):
                in_block_comment = "*/" not in line
                continue
            if line.startswith("//"):
                continue

        if path.suffix in {".py", ".sh", ".yaml", ".yml"} and line.startswith("#"):
            continue

        lines.append(line)

    return lines


def added_lines(base_file: Path | None, variant_file: Path) -> int:
    variant_lines = code_lines(variant_file)
    if base_file is None or not base_file.exists():
        return len(variant_lines)

    additions = 0
    matcher = difflib.SequenceMatcher(a=code_lines(base_file), b=variant_lines)
    for tag, _, _, variant_start, variant_end in matcher.get_opcodes():
        if tag in {"insert", "replace"}:
            additions += variant_end - variant_start
    return additions


def category(relative_path: Path) -> str:
    path = relative_path.as_posix()
    if path == "web/chat-ia.js":
        return "Configuracion del widget"
    if path == "web/plantilla.html":
        return "Enlazado del asistente"
    if path == "backend/aikit.yaml":
        return "Configuracion del framework"
    if path.startswith("backend/services/") or path.endswith("catalogo.py"):
        return "Logica de dominio"
    if path.startswith("backend/"):
        return "Backend y orquestacion"
    return "Cliente web"


def widget_matches_framework(case_root: Path, framework_root: Path) -> bool:
    for name in WIDGET_FILES:
        copied = case_root / "aikit" / "web" / name
        original = framework_root / name
        if not copied.exists() or not original.exists():
            return False
        if hashlib.sha256(copied.read_bytes()).digest() != hashlib.sha256(original.read_bytes()).digest():
            return False
    return True


def revision(codigo_root: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(codigo_root), "rev-parse", "HEAD"], text=True
    ).strip()


def render_report(
    case_root: Path, codigo_root: Path, script_path: Path, rows: dict[str, list[tuple[str, str, int]]]
) -> str:
    totals = {variant: sum(row[2] for row in values) for variant, values in rows.items()}
    report = [
        "# Recuento reproducible de codigo de integracion",
        "",
        f"- Fecha de ejecucion: {date.today().isoformat()}",
        f"- Revision evaluada de `codigo/`: `{revision(codigo_root)}`",
        f"- Herramienta de recuento: `{script_path.name}` (SHA-256: `{hashlib.sha256(script_path.read_bytes()).hexdigest()}`)",
        f"- Entorno: Python {platform.python_version()} sobre {platform.system()} {platform.release()}.",
        "- Aplicacion base: `examples/armarios-mario/base/`",
        "- Variantes: `bedrock`, `langchain` y `aikit`.",
        "- Regla de recuento: lineas no vacias ni comentarios de archivos `.py`, `.js`, `.css`, `.html`, `.yaml`, `.yml` y `.sh`.",
        "- Comparacion: se cuentan solo las lineas anadidas o modificadas de cada variante respecto a `base/`; las eliminaciones no se contabilizan.",
        "- Exclusiones: `aikit/web/chat-popup.js` y `aikit/web/chat-popup.css`, aportados sin modificacion por AiKit. El script verifica su igualdad binaria con `aikit/ui/chat-popup/` antes de medir.",
        "",
        "## Totales",
        "",
        "| Variante | Lineas de codigo de integracion |",
        "|---|---:|",
    ]
    report.extend(f"| {variant} | {totals[variant]} |" for variant in VARIANTS)

    for variant in VARIANTS:
        report.extend([
            "",
            f"## {variant}",
            "",
            "| Categoria | Fichero | Lineas anadidas o modificadas |",
            "|---|---|---:|",
        ])
        report.extend(
            f"| {item_category} | `{path}` | {count} |"
            for item_category, path, count in rows[variant]
        )

    return "\n".join(report) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    case_root = Path(__file__).resolve().parent
    codigo_root = case_root.parents[1]
    framework_root = codigo_root / "aikit" / "ui" / "chat-popup"
    output = arguments.output

    if not widget_matches_framework(case_root, framework_root):
        raise SystemExit("El widget de AiKit no coincide con la copia distribuida por el framework.")

    base_root = case_root / "base"
    rows: dict[str, list[tuple[str, str, int]]] = defaultdict(list)
    for variant in VARIANTS:
        variant_root = case_root / variant
        for file_path in sorted(variant_root.rglob("*")):
            if not file_path.is_file() or file_path.suffix not in SOURCE_EXTENSIONS:
                continue
            relative_path = file_path.relative_to(variant_root)
            if variant == "aikit" and relative_path.as_posix() in {f"web/{name}" for name in WIDGET_FILES}:
                continue
            count = added_lines(base_root / relative_path, file_path)
            if count:
                rows[variant].append((category(relative_path), relative_path.as_posix(), count))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_report(case_root, codigo_root, Path(__file__).resolve(), rows), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
