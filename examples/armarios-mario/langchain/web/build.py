#!/usr/bin/env python3
"""Genera las fichas de producto y sus ilustraciones a partir de catalogo.csv.

La disposicion comun vive en plantilla.html, de modo que cualquier cambio de
maquetacion se declara una sola vez y no en cada ficha.
"""

import csv
import html
from pathlib import Path

WEB = Path(__file__).resolve().parent

COLORS = {
    "roble claro": "#d8b98a",
    "roble oscuro": "#8a5f36",
    "blanco mate": "#f0efe9",
    "gris grafito": "#565b60",
    "nogal": "#6b4a2f",
    "arena": "#d9c9a8",
    "cerezo": "#8f4033",
    "verde menta": "#a9d8c3",
    "azul cielo": "#a8c9e6",
}

SUBTITULOS = {
    "modelo1": "Armario de 3 puertas para dormitorio principal con barra doble, cajonera y gran capacidad.",
    "modelo2": "Solución esquinera de fondo ampliado que aprovecha el rincón sin invadir la habitación.",
    "modelo3": "Modelo de entrada, compacto y ligero, pensado para habitaciones juveniles o de invitados.",
    "modelo4": "Gran formato con puertas correderas amortiguadas, indicado para techos altos y espacios diáfanos.",
    "modelo5": "Configuración estándar equilibrada, con balda superior de maletero.",
    "modelo6": "Armario infantil de cantos redondeados y anclaje reforzado, disponible en colores vivos.",
    "modelo7": "Fabricado en madera maciza de pino con acabado barnizado a mano, bajo pedido.",
    "modelo8": "Auxiliar de fondo reducido para pasillos y espacios estrechos; no requiere anclaje.",
    "modelo9": "Gama alta con puertas de espejo integradas e iluminación LED interior.",
}

CONSEJOS = {
    "modelo1": "Consejo de compra: si necesitas guardar cajas pesadas o maletas, este modelo soporta más carga por balda que la media.",
    "modelo2": "Consejo de compra: mide el rincón antes de comprar, ya que el fondo de 95 cm requiere espacio de apertura lateral.",
    "modelo3": "Consejo de compra: es la opción más económica con dos puertas abatibles; verifica que dispones de 60 cm de apertura frontal.",
    "modelo4": "Consejo de compra: al ser de puertas correderas no necesita espacio de apertura, pero si un hueco de 250 cm de alto.",
    "modelo5": "Consejo de compra: equilibrio entre precio y capacidad, con la balda superior pensada para maletas.",
    "modelo6": "Consejo de compra: el anclaje reforzado es obligatorio en habitaciones infantiles por seguridad.",
    "modelo7": "Consejo de compra: la madera maciza admite lijado y rebarnizado, por lo que su vida útil supera a la del tablero.",
    "modelo8": "Consejo de compra: con 40 cm de fondo admite perchas colgadas en paralelo, no perchas estándar de frente.",
    "modelo9": "Consejo de compra: las puertas con espejo aumentan la sensación de amplitud en habitaciones pequeñas.",
}


def capitalizar(texto: str) -> str:
    return texto[:1].upper() + texto[1:] if texto else texto


def color_hex(nombre: str) -> str:
    return COLORS.get(nombre.strip().lower(), "#cbbba4")


def oscurecer(color: str, factor: float) -> str:
    r = int(int(color[1:3], 16) * factor)
    g = int(int(color[3:5], 16) * factor)
    b = int(int(color[5:7], 16) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def construir_svg(fila: dict) -> str:
    ancho, alto = int(fila["ancho_cm"]), int(fila["alto_cm"])
    puertas, baldas = int(fila["puertas"]), int(fila["baldas"])
    corredera = "correr" in fila["tipo_puerta"].lower()
    base = color_hex(fila["colores"].split("|")[0])
    borde, tirador = oscurecer(base, 0.7), oscurecer(base, 0.45)

    lienzo_w, lienzo_h = 640, 480
    escala = min(420 / ancho, 380 / alto)
    w, h = ancho * escala, alto * escala
    x, y = (lienzo_w - w) / 2, lienzo_h - 40 - h

    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {lienzo_w} {lienzo_h}" role="img" aria-label="{html.escape(fila["nombre"])}">',
        f'<rect width="{lienzo_w}" height="{lienzo_h}" fill="#f4f6f8"/>',
        f'<ellipse cx="{lienzo_w/2:.0f}" cy="{lienzo_h-34:.0f}" rx="{w*0.62:.0f}" ry="12" fill="#dfe4e8"/>',
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="4" fill="{base}" stroke="{borde}" stroke-width="3"/>',
    ]

    if puertas == 0:
        partes.append(f'<rect x="{x+8:.1f}" y="{y+8:.1f}" width="{w-16:.1f}" height="{h-16:.1f}" fill="#ffffff" opacity="0.55"/>')
        for i in range(1, baldas + 1):
            sy = y + 8 + (h - 16) * i / (baldas + 1)
            partes.append(f'<line x1="{x+8:.1f}" y1="{sy:.1f}" x2="{x+w-8:.1f}" y2="{sy:.1f}" stroke="{borde}" stroke-width="3"/>')
        partes.append(f'<line x1="{x+w*0.55:.1f}" y1="{y+30:.1f}" x2="{x+w-14:.1f}" y2="{y+30:.1f}" stroke="{tirador}" stroke-width="4" stroke-linecap="round"/>')
    else:
        panel = w / puertas
        for i in range(puertas):
            px = x + i * panel
            partes.append(f'<rect x="{px+3:.1f}" y="{y+3:.1f}" width="{panel-6:.1f}" height="{h-6:.1f}" rx="3" fill="{base}" stroke="{borde}" stroke-width="2"/>')
            if "espejo" in fila["nombre"].lower() and i in (1, puertas - 2):
                partes.append(f'<rect x="{px+12:.1f}" y="{y+14:.1f}" width="{panel-24:.1f}" height="{h-28:.1f}" fill="#dbe7ef" opacity="0.9" stroke="{borde}"/>')
            if corredera:
                partes.append(f'<rect x="{px+panel*0.3:.1f}" y="{y+h/2-22:.1f}" width="6" height="44" rx="3" fill="{tirador}"/>')
            else:
                hx = px + panel - 14 if i < puertas - 1 else px + 14
                partes.append(f'<circle cx="{hx:.1f}" cy="{y+h/2:.1f}" r="5" fill="{tirador}"/>')
        if corredera:
            partes.append(f'<line x1="{x:.1f}" y1="{y+6:.1f}" x2="{x+w:.1f}" y2="{y+6:.1f}" stroke="{tirador}" stroke-width="3"/>')
            partes.append(f'<line x1="{x:.1f}" y1="{y+h-6:.1f}" x2="{x+w:.1f}" y2="{y+h-6:.1f}" stroke="{tirador}" stroke-width="3"/>')

    partes.append(f'<rect x="{x+6:.1f}" y="{y+h:.1f}" width="14" height="10" fill="{borde}"/>')
    partes.append(f'<rect x="{x+w-20:.1f}" y="{y+h:.1f}" width="14" height="10" fill="{borde}"/>')
    partes.append(
        f'<text x="{lienzo_w/2:.0f}" y="{lienzo_h-8:.0f}" text-anchor="middle" '
        f'font-family="system-ui, sans-serif" font-size="15" fill="#55636d">'
        f'{ancho} x {alto} x {fila["fondo_cm"]} cm</text>'
    )
    partes.append("</svg>")
    return "\n".join(partes)


def construir_especificaciones(fila: dict) -> str:
    puertas = int(fila["puertas"])
    campos = [
        ("Disponibilidad", capitalizar(fila["disponibilidad"])),
        ("Dimensiones", f'{fila["ancho_cm"]} x {fila["alto_cm"]} x {fila["fondo_cm"]} cm'),
        ("Colores", ", ".join(capitalizar(c) for c in fila["colores"].split("|") if c)),
        ("Baldas", f'{fila["baldas"]} baldas'),
        ("Carga por balda", f'{fila["peso_max_por_balda_kg"]} kg'),
        ("Peso total máximo", f'{fila["peso_total_max_kg"]} kg'),
        ("Material", capitalizar(fila["material"])),
        ("Puertas", f'{puertas} {fila["tipo_puerta"]}' if puertas else "Sin puertas (sistema abierto)"),
        ("Montaje", f'{fila["montaje_min"]} min'),
        ("Habitación mínima", f'{int(fila["ancho_cm"]) + 30} cm ancho x {int(fila["fondo_cm"]) + 30} cm fondo'),
        ("Anclaje a pared", capitalizar(fila["requiere_anclaje_pared"])),
        ("Stock", f'{fila["stock"]} unidades'),
    ]
    return "\n" + "\n".join(
        f"                <div><strong>{k}</strong>{html.escape(v)}</div>" for k, v in campos
    ) + "\n            "


def main() -> None:
    filas = list(csv.DictReader((WEB / "catalogo.csv").open(encoding="utf-8")))
    plantilla = (WEB / "plantilla.html").read_text(encoding="utf-8")
    (WEB / "img").mkdir(exist_ok=True)

    for i, fila in enumerate(filas):
        modelo = fila["modelo"]
        valores = {
            "titulo": f'{modelo.capitalize()} | {fila["nombre"]}',
            "modelo": modelo,
            "nombre": html.escape(fila["nombre"]),
            "subtitulo": SUBTITULOS[modelo],
            "precio": fila["precio_eur"],
            "disponibilidad": capitalizar(fila["disponibilidad"]),
            "envio": fila["envio_dias"],
            "especificaciones": construir_especificaciones(fila),
            "consejo": CONSEJOS[modelo],
        }
        pagina = plantilla
        for clave, valor in valores.items():
            pagina = pagina.replace("{{" + clave + "}}", valor)

        (WEB / f"{modelo}.html").write_text(pagina, encoding="utf-8")
        (WEB / "img" / f"{modelo}.svg").write_text(construir_svg(fila), encoding="utf-8")

    print(f"generadas {len(filas)} fichas con sus ilustraciones")


if __name__ == "__main__":
    main()
