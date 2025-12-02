# app/main.py
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import openai
from pathlib import Path
import yaml
import importlib
import inspect

from tools import build_tools_from_services
from executor import execute_tool_call
from services.base import BaseService
from contextlib import asynccontextmanager

#import colored_traceback
#colored_traceback.add_hook()
services: Dict[str, BaseService] = {}        # se llenan en startup()
conversation_store: Dict[str, List[Dict]] = {}  # historial por conversation_id


def load_services(config_path: str = "aikit.yaml"):
	"""
	Lee el YAML y carga dinámicamente los servicios definidos.
	"""
	global services

	config_file = Path(config_path)
	if not config_file.exists():
		raise RuntimeError(f"Config file {config_path} no encontrado")

	cfg = yaml.safe_load(config_file.read_text())

	loaded = {}

	for svc_cfg in cfg.get("services", []):
		name = svc_cfg["name"]
		module_name = svc_cfg["module"]
		class_name = svc_cfg["class"]

		module = importlib.import_module(module_name)
		cls = getattr(module, class_name, None)
		if cls is None:
			raise RuntimeError(f"No se encontró la clase {class_name} en {module_name}")

		if not inspect.isclass(cls) or not issubclass(cls, BaseService):
			raise RuntimeError(f"{class_name} no es un BaseService válido")

		instance = cls()
		loaded[name] = instance
		print(f"[startup] Servicio cargado: {name} ({module_name}.{class_name})")

	services = loaded


@asynccontextmanager
async def lifespan(app: FastAPI):
	"""
	FastAPI llamará automáticamente a esta función al arrancar y cerrar.
	"""
	# Startup
	load_services()
	yield
	# Shutdown (si necesitas hacer limpieza)


app = FastAPI(lifespan=lifespan)


@app.get("/services")
def list_services():
	"""
	Endpoint de prueba para ver qué servicios y métodos se han cargado.
	"""
	return {
		name: {
			"description": svc.description,
			"methods": [m.dict() for m in svc.list_methods()],
		}
		for name, svc in services.items()
	}


# Ejemplo opcional: endpoint para llamar un método directamente (útil mientras montas la IA)
from pydantic import BaseModel
from typing import Any, Dict


class ServiceCallRequest(BaseModel):
	service: str
	method: str
	params: Dict[str, Any] = {}


@app.post("/call")
def call_service(req: ServiceCallRequest):
	svc = services.get(req.service)
	if not svc:
		raise HTTPException(status_code=404, detail=f"Servicio {req.service} no encontrado")

	try:
		method = svc.get_method(req.method)
	except AttributeError as e:
		raise HTTPException(status_code=404, detail=str(e))

	try:
		result = method(**req.params)
	except TypeError as e:
		raise HTTPException(status_code=400, detail=f"Error de parámetros: {e}")

	return {"result": result}



class ChatRequest(BaseModel):
	message: str
	conversation_id: Optional[str] = None


def get_history(conv_id: Optional[str]) -> List[Dict[str, Any]]:
	if not conv_id:
		return []
	return conversation_store.setdefault(conv_id, [])


def save_history(conv_id: Optional[str], messages: List[Dict[str, Any]]):
	if not conv_id:
		return
	conversation_store.setdefault(conv_id, []).extend(messages)


@app.post("/chat")
async def chat(req: ChatRequest):
	conv_id = req.conversation_id or "anon"
	history = get_history(conv_id)

	# 1) Construimos el array de mensajes
	messages: List[Dict[str, Any]] = []
	messages.extend(history)
	messages.append({"role": "user", "content": req.message})

	tools = build_tools_from_services(services)
	print(f"tools:\n{tools}")

	# 2) Agent loop
	MAX_STEPS = 5
	steps = 0
	while True:
		steps += 1
		print(f"* STEP {steps}")
		if steps > MAX_STEPS:
			assistant_answer = "He realizado demasiados pasos internos y no puedo continuar."
			messages.append({"role": "assistant", "content": assistant_answer})
			save_history(conv_id, messages[len(history):])
			return {"answer": assistant_answer, "conversation_id": conv_id}

		# Llamada a la IA con tools activadas
		response = openai.chat.completions.create(
			#model="gpt-4.1",  # o el que uses con tool calling
			#model="gpt-5-chat-latest",  # o el que uses con tool calling
			#model="gpt-5-mini",
			model="gpt-4o-mini",
			messages=messages,
			tools=tools,
			tool_choice="auto",
		)

		msg = response.choices[0].message

		# ¿Hay tool_calls?
		tool_calls = getattr(msg, "tool_calls", None)

		if tool_calls:
			# Guardamos el mensaje "assistant" que pide usar herramientas
			messages.append({
				"role": "assistant",
				"content": msg.content or "",
				"tool_calls": [tc.to_dict() if hasattr(tc, "to_dict") else tc for tc in tool_calls],
			})

			# Ejecutar cada tool_call y añadir su resultado
			for tc in tool_calls:
				tool_result = execute_tool_call(services, tc)

				messages.append({
					"role": "tool",
					"tool_call_id": tool_result["tool_call_id"],
					"name": tool_result["name"],
					"content": tool_result["content"],
				})

			# siguiente iteración: la IA verá también los mensajes de tipo "tool"
			continue

		# Si no hay tool_calls, ya tenemos respuesta final para el usuario
		assistant_answer = msg.content
		messages.append({"role": "assistant", "content": assistant_answer})

		# Guardar en el historial sólo lo nuevo (desde donde empezó esta petición)
		save_history(conv_id, messages[len(history):])

		return {
			"answer": assistant_answer,
			"conversation_id": conv_id,
		}


if __name__ == "__main__":
	import uvicorn
	uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
