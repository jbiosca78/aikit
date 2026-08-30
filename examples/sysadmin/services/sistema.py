"""Servicio de consulta del estado del sistema.

Todas las operaciones son de solo lectura y estan acotadas a un conjunto cerrado de
acciones. El servicio no ejecuta ordenes recibidas del modelo ni construye ordenes a
partir de texto libre: cada metodo invoca una utilidad concreta con argumentos validados.
"""

import os
import re
import shutil
import subprocess
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, List

from aikit.core.service_contract import ServiceContract, MethodSchema

# Directorios cuyos ficheros pueden consultarse. Cualquier ruta fuera de ellos se rechaza.
RUTAS_PERMITIDAS = [
    Path(p).resolve()
    for p in os.getenv("AIKIT_RUTAS_PERMITIDAS", "/var/log:/etc").split(":")
    if p
]

NOMBRE_UNIDAD_RE = re.compile(r"^[A-Za-z0-9@._-]{1,64}$")
MAX_LINEAS = 200

# Ficheros excluidos aunque residan dentro de un directorio autorizado: contienen
# credenciales o material criptografico y no deben llegar nunca al modelo.
PATRONES_EXCLUIDOS = (
    "shadow",
    "gshadow",
    "sudoers",
    "*.key",
    "*.pem",
    "*_rsa",
    "*_ed25519",
    "*.p12",
    "*.pfx",
    ".env",
    "*.env",
    "credentials",
    "htpasswd",
)
DIRECTORIOS_EXCLUIDOS = ("ssl", "ssh", "pki", "secrets", "private")


def _es_sensible(ruta: Path) -> bool:
    nombre = ruta.name.lower()
    if any(fnmatch(nombre, patron) for patron in PATRONES_EXCLUIDOS):
        return True
    return any(parte.lower() in DIRECTORIOS_EXCLUIDOS for parte in ruta.parts)


def _ruta_permitida(ruta: str) -> Path | None:
    """Resuelve la ruta y comprueba que quede dentro de los directorios autorizados."""
    try:
        candidata = Path(ruta).expanduser().resolve()
    except (OSError, RuntimeError):
        return None
    if _es_sensible(candidata):
        return None
    for permitida in RUTAS_PERMITIDAS:
        if candidata == permitida or permitida in candidata.parents:
            return candidata
    return None


class Service(ServiceContract):
    name = "sistema"
    description = "Consulta del estado del servidor: discos, memoria, servicios y registros."

    def list_methods(self) -> List[MethodSchema]:
        return [
            MethodSchema(
                name="get_disk_usage",
                description=(
                    "Devuelve el espacio ocupado y disponible en los puntos de montaje. "
                    "Uselo cuando pregunten por espacio en disco o por particiones llenas."
                ),
                params_schema={},
                required_params=[],
                returns_schema={"type": "array", "items": {"type": "object"}},
            ),
            MethodSchema(
                name="get_memory_usage",
                description="Devuelve la memoria total, usada y disponible del sistema, y la carga media.",
                params_schema={},
                required_params=[],
                returns_schema={"type": "object", "additionalProperties": True},
            ),
            MethodSchema(
                name="get_service_status",
                description=(
                    "Devuelve el estado de un servicio gestionado por systemd. "
                    "Uselo cuando pregunten si un servicio esta activo o por que se ha detenido."
                ),
                params_schema={
                    "unit": {
                        "type": "string",
                        "description": "Nombre de la unidad, por ejemplo 'nginx' o 'sshd'.",
                    }
                },
                required_params=["unit"],
                returns_schema={"type": "object", "additionalProperties": True},
            ),
            MethodSchema(
                name="list_files",
                description=(
                    "Lista los ficheros de un directorio autorizado, con su tamano y fecha. "
                    "Uselo para localizar ficheros de registro o de configuracion."
                ),
                params_schema={
                    "path": {
                        "type": "string",
                        "description": "Ruta del directorio, por ejemplo '/var/log'.",
                    }
                },
                required_params=["path"],
                returns_schema={"type": "object", "additionalProperties": True},
            ),
            MethodSchema(
                name="tail_file",
                description=(
                    "Devuelve las ultimas lineas de un fichero de texto autorizado. "
                    "Uselo para revisar registros recientes y localizar errores."
                ),
                params_schema={
                    "path": {"type": "string", "description": "Ruta del fichero."},
                    "lines": {
                        "type": "integer",
                        "description": f"Numero de lineas a devolver, entre 1 y {MAX_LINEAS}.",
                    },
                },
                required_params=["path"],
                returns_schema={"type": "object", "additionalProperties": True},
            ),
            MethodSchema(
                name="get_allowed_paths",
                description="Devuelve los directorios que el asistente tiene autorizado consultar.",
                params_schema={},
                required_params=[],
                returns_schema={"type": "array", "items": {"type": "string"}},
            ),
        ]

    def get_allowed_paths(self) -> List[str]:
        return [str(p) for p in RUTAS_PERMITIDAS]

    def get_disk_usage(self) -> List[Dict[str, Any]]:
        resultado: List[Dict[str, Any]] = []
        for linea in Path("/proc/mounts").read_text(encoding="utf-8").splitlines():
            partes = linea.split()
            if len(partes) < 3 or not partes[1].startswith("/"):
                continue
            if partes[2] in ("proc", "sysfs", "devtmpfs", "cgroup2", "tmpfs", "devpts", "securityfs", "pstore", "efivarfs", "bpf", "tracefs", "debugfs", "configfs", "fusectl", "mqueue", "hugetlbfs", "ramfs", "autofs", "binfmt_misc", "nsfs", "squashfs"):
                continue
            try:
                uso = shutil.disk_usage(partes[1])
            except OSError:
                continue
            resultado.append({
                "punto_montaje": partes[1],
                "sistema_ficheros": partes[2],
                "total_gb": round(uso.total / 1024**3, 1),
                "usado_gb": round(uso.used / 1024**3, 1),
                "libre_gb": round(uso.free / 1024**3, 1),
                "porcentaje_uso": round(uso.used * 100 / uso.total) if uso.total else 0,
            })
        return resultado

    def get_memory_usage(self) -> Dict[str, Any]:
        valores: Dict[str, int] = {}
        for linea in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            clave, _, resto = linea.partition(":")
            numero = resto.strip().split(" ")[0]
            if numero.isdigit():
                valores[clave] = int(numero)

        total = valores.get("MemTotal", 0)
        disponible = valores.get("MemAvailable", 0)
        carga = os.getloadavg()
        return {
            "total_mb": round(total / 1024),
            "disponible_mb": round(disponible / 1024),
            "usada_mb": round((total - disponible) / 1024),
            "porcentaje_uso": round((total - disponible) * 100 / total) if total else 0,
            "carga_media": {"1_min": carga[0], "5_min": carga[1], "15_min": carga[2]},
        }

    def get_service_status(self, unit: str) -> Dict[str, Any]:
        nombre = unit.strip()
        if not NOMBRE_UNIDAD_RE.match(nombre):
            return {"error": "nombre de unidad no valido", "unidad": unit}
        if not shutil.which("systemctl"):
            return {"error": "systemd no esta disponible en este sistema"}

        # Argumentos fijos y nombre validado: no se construye ninguna orden a partir de texto libre.
        proceso = subprocess.run(
            ["systemctl", "show", nombre, "--no-page",
             "--property=ActiveState,SubState,UnitFileState,ExecMainStartTimestamp,Description"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proceso.returncode != 0:
            return {"encontrado": False, "unidad": nombre}

        datos = dict(
            linea.split("=", 1) for linea in proceso.stdout.strip().splitlines() if "=" in linea
        )
        return {
            "encontrado": True,
            "unidad": nombre,
            "descripcion": datos.get("Description", ""),
            "estado": datos.get("ActiveState", ""),
            "subestado": datos.get("SubState", ""),
            "arranque_automatico": datos.get("UnitFileState", ""),
            "inicio": datos.get("ExecMainStartTimestamp", ""),
        }

    def list_files(self, path: str) -> Dict[str, Any]:
        destino = _ruta_permitida(path)
        if destino is None:
            return {"error": "ruta no autorizada", "rutas_permitidas": self.get_allowed_paths()}
        if not destino.is_dir():
            return {"error": "la ruta no es un directorio", "ruta": str(destino)}

        ficheros = []
        try:
            for elemento in sorted(destino.iterdir()):
                if _es_sensible(elemento):
                    continue
                try:
                    info = elemento.stat()
                except OSError:
                    continue
                ficheros.append({
                    "nombre": elemento.name,
                    "tipo": "directorio" if elemento.is_dir() else "fichero",
                    "tamano_kb": round(info.st_size / 1024, 1),
                    "modificado": int(info.st_mtime),
                })
        except PermissionError:
            return {"error": "sin permisos de lectura", "ruta": str(destino)}

        return {"ruta": str(destino), "total": len(ficheros), "ficheros": ficheros[:200]}

    def tail_file(self, path: str, lines: int = 50) -> Dict[str, Any]:
        destino = _ruta_permitida(path)
        if destino is None:
            return {"error": "ruta no autorizada", "rutas_permitidas": self.get_allowed_paths()}
        if not destino.is_file():
            return {"error": "la ruta no es un fichero", "ruta": str(destino)}

        cantidad = max(1, min(int(lines or 50), MAX_LINEAS))
        try:
            with destino.open("r", encoding="utf-8", errors="replace") as fh:
                contenido = fh.readlines()[-cantidad:]
        except PermissionError:
            return {"error": "sin permisos de lectura", "ruta": str(destino)}

        return {
            "ruta": str(destino),
            "lineas_devueltas": len(contenido),
            "contenido": "".join(contenido),
        }
