"""Publica las herramientas de un servidor MCP como un servicio de dominio de AiKit.

Es un ejemplo de extensibilidad: el nucleo no se modifica. Construye las herramientas a
partir de `list_methods()` y las ejecuta resolviendo el metodo con `getattr`, asi que un
servicio que descubre sus metodos en tiempo de ejecucion y los resuelve con `__getattr__`
encaja en el contrato sin cambiar una linea del framework.

Requiere el SDK oficial (`pip install mcp`) y un servidor MCP accesible. Si falta alguna
de las dos cosas el servicio no publica herramientas y el resto de AiKit sigue
funcionando, igual que el servicio `music` sin un Mopidy delante.

Cada fichero representa un servidor. Para conectar con otro, copia este modulo con otro
nombre, ajusta el bloque de configuracion y registralo como un servicio mas:

    services:
      - name: mcp_ficheros
        module: services.mcp_ficheros
      - name: mcp_incidencias
        module: services.mcp_incidencias

El prefijo de las herramientas sale del `name` del YAML, de modo que dos copias conviven
sin colisionar: `mcp_ficheros__read_file`, `mcp_incidencias__read_file`.
"""
from __future__ import annotations

import asyncio
import logging
import re
import shlex
import threading
from typing import Any, Callable, Dict, List, Optional

from aikit.core.service_contract import ServiceContract, MethodSchema

# --- Configuracion del servidor ---------------------------------------------

# NOMBRE debe coincidir con el `name` del aikit.yaml: de ahi sale el prefijo de las
# herramientas y el margen que hay que reservar al acortarlas.
NOMBRE = "mcp"
DESCRIPCION = "Herramientas publicadas por un servidor MCP externo."

# Transporte stdio: ejecutable del servidor y sus argumentos en una sola cadena.
COMANDO = "npx"
ARGUMENTOS = "-y @modelcontextprotocol/server-filesystem /tmp"

# Transporte HTTP. Si se indica una URL, tiene prioridad sobre el comando anterior.
URL = ""

TIMEOUT_CONEXION = 60.0
TIMEOUT_LLAMADA = 30.0

# ----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# Los proveedores aceptan nombres de herramienta mucho mas restrictivos que MCP.
_CARACTER_NO_VALIDO = re.compile(r"[^a-zA-Z0-9_-]")


class _BucleDedicado:
    """Bucle de eventos propio en un hilo aparte.

    El nucleo invoca las herramientas de forma sincrona (`method(**args)`) y el SDK de
    MCP es asincrono. La sesion vive aqui para que el proceso del servidor siga abierto
    entre llamadas en lugar de levantarse y cerrarse en cada una.
    """

    def __init__(self) -> None:
        self._bucle = asyncio.new_event_loop()
        hilo = threading.Thread(target=self._servir, name="aikit-mcp", daemon=True)
        hilo.start()

    def _servir(self) -> None:
        asyncio.set_event_loop(self._bucle)
        self._bucle.run_forever()

    def ejecutar(self, corutina, timeout: float) -> Any:
        futuro = asyncio.run_coroutine_threadsafe(corutina, self._bucle)
        return futuro.result(timeout)


class Service(ServiceContract):
    name = NOMBRE
    description = DESCRIPCION

    def __init__(self) -> None:
        self._bucle: Optional[_BucleDedicado] = None
        self._sesion: Optional[Any] = None
        self._pila: Optional[Any] = None
        self._metodos: Optional[List[MethodSchema]] = None
        # nombre saneado -> nombre original en el servidor MCP
        self._originales: Dict[str, str] = {}

    # --- contrato -----------------------------------------------------------

    def list_methods(self) -> List[MethodSchema]:
        if self._metodos is not None:
            return self._metodos

        try:
            herramientas = self._descubrir()
        except Exception as exc:
            # Un servidor MCP caido no debe impedir que arranque el resto de AiKit.
            logger.warning(
                "mcp no disponible servicio=%s, no publica herramientas: %s", self.name, exc
            )
            self._metodos = []
            return self._metodos

        metodos: List[MethodSchema] = []
        for herramienta in herramientas:
            metodo = self._a_method_schema(herramienta)
            if metodo is not None:
                metodos.append(metodo)

        logger.info("mcp tools descubiertas servicio=%s count=%s", self.name, len(metodos))
        self._metodos = metodos
        return self._metodos

    def __getattr__(self, nombre: str) -> Callable[..., Any]:
        """Resuelve como invocable cualquier herramienta descubierta en el servidor.

        `get_method` del contrato usa `getattr`, de modo que basta con sintetizar aqui
        el metodo para que el nucleo pueda ejecutarlo sin saber que hay MCP detras.
        """
        # Imprescindible: los atributos internos y los dunder deben fallar de forma
        # normal, o `__init__` y la introspeccion entrarian en recursion.
        if nombre.startswith("_"):
            raise AttributeError(nombre)

        if self._metodos is None:
            self.list_methods()
        if nombre not in self._originales:
            raise AttributeError(f"Herramienta MCP {nombre} no encontrada")

        original = self._originales[nombre]

        def invocar(**kwargs: Any) -> Any:
            return self._llamar(original, kwargs)

        invocar.__name__ = nombre
        return invocar

    # --- traduccion ---------------------------------------------------------

    def _a_method_schema(self, herramienta: Any) -> Optional[MethodSchema]:
        original = getattr(herramienta, "name", "") or ""
        if not original:
            return None

        # El nucleo antepone "<servicio>__", y los proveedores limitan el nombre de la
        # herramienta a 64 caracteres: el margen hay que descontarlo aqui.
        limite = 64 - len(self.name) - 2
        saneado = _CARACTER_NO_VALIDO.sub("_", original)[:limite]
        if saneado in self._originales and self._originales[saneado] != original:
            logger.warning("colision de nombre al sanear herramienta mcp name=%s", original)
            return None
        self._originales[saneado] = original

        # `inputSchema` es un JSON Schema completo; AiKit espera solo las propiedades,
        # porque el nucleo ya envuelve el objeto al construir la herramienta.
        esquema = getattr(herramienta, "inputSchema", None) or {}
        propiedades = esquema.get("properties", {}) if isinstance(esquema, dict) else {}
        obligatorios = esquema.get("required", []) if isinstance(esquema, dict) else []

        salida = getattr(herramienta, "outputSchema", None)
        descripcion = getattr(herramienta, "description", "") or original

        return MethodSchema(
            name=saneado,
            description=descripcion,
            params_schema=propiedades,
            required_params=list(obligatorios),
            returns_schema=salida if isinstance(salida, dict) else {"type": "string"},
        )

    @staticmethod
    def _a_resultado(respuesta: Any) -> Any:
        """Reduce la respuesta de MCP a algo que el nucleo pueda serializar."""
        estructurado = getattr(respuesta, "structuredContent", None)
        if estructurado is not None:
            return estructurado

        textos = [
            bloque.text
            for bloque in getattr(respuesta, "content", []) or []
            if getattr(bloque, "type", None) == "text" and getattr(bloque, "text", None)
        ]
        if textos:
            return "\n".join(textos) if len(textos) > 1 else textos[0]
        return {"content": str(getattr(respuesta, "content", ""))}

    # --- sesion -------------------------------------------------------------

    def _descubrir(self) -> List[Any]:
        self._conectar()
        respuesta = self._bucle.ejecutar(self._sesion.list_tools(), TIMEOUT_LLAMADA)
        return list(getattr(respuesta, "tools", []) or [])

    def _llamar(self, herramienta: str, argumentos: Dict[str, Any]) -> Any:
        self._conectar()
        logger.debug("mcp tools/call servicio=%s tool=%s args=%s", self.name, herramienta, argumentos)
        respuesta = self._bucle.ejecutar(
            self._sesion.call_tool(herramienta, argumentos), TIMEOUT_LLAMADA
        )
        if getattr(respuesta, "isError", False):
            raise RuntimeError(f"El servidor MCP devolvio un error en {herramienta}")
        return self._a_resultado(respuesta)

    def _conectar(self) -> None:
        if self._sesion is not None:
            return
        if self._bucle is None:
            self._bucle = _BucleDedicado()
        self._bucle.ejecutar(self._abrir(), TIMEOUT_CONEXION)

    async def _abrir(self) -> None:
        from contextlib import AsyncExitStack

        from mcp import ClientSession

        pila = AsyncExitStack()

        if URL:
            from mcp.client.streamable_http import streamablehttp_client

            canales = await pila.enter_async_context(streamablehttp_client(URL))
            lectura, escritura = canales[0], canales[1]
        else:
            from mcp import StdioServerParameters
            from mcp.client.stdio import stdio_client

            if not COMANDO:
                await pila.aclose()
                raise RuntimeError("define URL o COMANDO en la cabecera del modulo")
            parametros = StdioServerParameters(
                command=COMANDO,
                args=shlex.split(ARGUMENTOS),
            )
            lectura, escritura = await pila.enter_async_context(stdio_client(parametros))

        sesion = await pila.enter_async_context(ClientSession(lectura, escritura))
        await sesion.initialize()

        self._pila = pila
        self._sesion = sesion
        logger.info("mcp conectado servicio=%s transporte=%s", self.name, "http" if URL else "stdio")
