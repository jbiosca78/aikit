#!/usr/bin/env python3

# app/main.py
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
#from openai import OpenAI
from pathlib import Path
import yaml
import importlib
import importlib.util
import inspect
import os
import sys
import json
import logging
import re
from contextlib import asynccontextmanager
from aikit.core.engine_contract import validate_engine_contract
from aikit.core.service_contract import ServiceContract
from aikit.core.history import HistoryStore, build_history_store
from aikit.core.auth import (
	build_session_config,
	issue_session_token,
	new_principal_id,
	resolve_principal,
)

#import colored_traceback
#colored_traceback.add_hook()
from rich.traceback import install
install(show_locals=True) # show_locals muestra variables locales en cada frame


# Variable global para almacenar el módulo cargado
engine = None
config: Dict[str, Any] = {}
services: Dict[str, ServiceContract] = {}
tools: List[Dict[str, Any]] = []
history_store: Optional[HistoryStore] = None
logger = logging.getLogger("aikit")


def setup_logging(log_cfg: Optional[Dict[str, Any]] = None) -> logging.Logger:
	for handler in list(logger.handlers):
		logger.removeHandler(handler)
		handler.close()

	log_level_name = "INFO"
	log_output = "stdout"
	if isinstance(log_cfg, dict):
		if isinstance(log_cfg.get("output"), str) and log_cfg.get("output", "").strip():
			log_output = log_cfg["output"].strip()
		if isinstance(log_cfg.get("level"), str) and log_cfg.get("level", "").strip():
			log_level_name = log_cfg["level"].strip().upper()

	log_level = getattr(logging, log_level_name, logging.INFO)
	logger.setLevel(log_level)

	if log_output.lower() == "stdout":
		handler = logging.StreamHandler(sys.stdout)
	else:
		handler = logging.FileHandler(Path(log_output), encoding="utf-8")
	handler.setLevel(log_level)

	formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")
	handler.setFormatter(formatter)
	logger.addHandler(handler)
	logger.propagate = False
	return logger


setup_logging()


def build_engine_prompt(config_engine: Dict[str, Any]) -> Optional[str]:
	"""
	Construye el prompt del engine desde YAML.
	Soporta:
	- engine.prompt: "texto"
	- engine.prompt:
	    - linea 1
	    - linea 2
	- engine.prompt:
	    text: "texto"
	- engine.prompt:
	    lines:
	      - linea 1
	      - linea 2
	"""
	prompt_cfg = config_engine.get("prompt")
	if not prompt_cfg:
		return None

	if isinstance(prompt_cfg, str):
		text = prompt_cfg.strip()
		return text or None

	if isinstance(prompt_cfg, list):
		lines = [str(x).strip() for x in prompt_cfg if str(x).strip()]
		return "\n".join(lines) if lines else None

	if isinstance(prompt_cfg, dict):
		if isinstance(prompt_cfg.get("text"), str):
			text = prompt_cfg["text"].strip()
			if text:
				return text
		lines_cfg = prompt_cfg.get("lines", [])
		if isinstance(lines_cfg, list):
			lines = [str(x).strip() for x in lines_cfg if str(x).strip()]
			return "\n".join(lines) if lines else None

	return None


def _parse_regex_flags(raw_flags: Any) -> int:
	if not isinstance(raw_flags, str):
		return 0

	flags = 0
	for token in [x.strip().upper() for x in raw_flags.split("|") if x.strip()]:
		if token == "IGNORECASE":
			flags |= re.IGNORECASE
		elif token == "MULTILINE":
			flags |= re.MULTILINE
		elif token == "DOTALL":
			flags |= re.DOTALL
		elif token == "ASCII":
			flags |= re.ASCII
	return flags


def apply_input_rewrites(message: str) -> str:
	rewritten = message
	rules = config.get("rewrites", []) if isinstance(config, dict) else []
	if not isinstance(rules, list):
		return rewritten

	for idx, rule in enumerate(rules):
		if not isinstance(rule, dict):
			continue

		pattern = rule.get("pattern")
		replacement = rule.get("replacement", "")
		if not isinstance(pattern, str) or not isinstance(replacement, str):
			continue

		flags = _parse_regex_flags(rule.get("flags", ""))
		count = rule.get("count", 0)
		if not isinstance(count, int) or count < 0:
			count = 0

		try:
			updated = re.sub(pattern, replacement, rewritten, count=count, flags=flags)
		except re.error as exc:
			logger.warning("invalid input rewrite rule index=%s error=%s", idx, exc)
			continue

		if updated != rewritten:
			rule_name = rule.get("name", f"rule_{idx}")
			logger.debug("input rewrite applied rule=%s before=%s after=%s", rule_name, rewritten, updated)
			rewritten = updated

	return rewritten


def load_services() -> Dict[str, ServiceContract]:
	"""
	Carga servicios configurados en YAML usando la convención:
	- name: stock -> modulo services.stock, clase Service
	"""
	loaded: Dict[str, ServiceContract] = {}
	for svc_cfg in config.get("services", []):
		name = svc_cfg["name"]
		module_name = svc_cfg.get("module", f"services.{name}")
		class_name = svc_cfg.get("class", "Service")

		module = importlib.import_module(module_name)
		cls = getattr(module, class_name, None)
		if cls is None:
			raise RuntimeError(f"No se encontró la clase {class_name} en {module_name}")
		if not inspect.isclass(cls) or not issubclass(cls, ServiceContract):
			raise RuntimeError(f"{class_name} no implementa ServiceContract")

		instance = cls()
		loaded[name] = instance
		logger.info("service loaded name=%s class=%s", name, f"{module_name}.{class_name}")

	return loaded


def build_tools_from_services(loaded_services: Dict[str, ServiceContract]) -> List[Dict[str, Any]]:
	built_tools: List[Dict[str, Any]] = []
	for svc_name, svc in loaded_services.items():
		for m in svc.list_methods():
			tool_name = f"{svc_name}__{m.name}"
			built_tools.append({
				"type": "function",
				"function": {
					"name": tool_name,
					"description": f"[Servicio: {svc_name}] {m.description}",
					"parameters": {
						"type": "object",
						"properties": m.params_schema,
						"required": list(m.required_params) if getattr(m, "required_params", None) else list(m.params_schema.keys()),
					},
				},
			})
	return built_tools


def init_tools() -> None:
	global services, tools
	services = load_services()
	tools = build_tools_from_services(services)
	logger.info("tools initialized count=%s", len(tools))


def build_effective_message(message: str, history: List[Dict[str, Any]], cfg: Dict[str, Any]) -> str:
	history_cfg = cfg.get("history", {}) if isinstance(cfg, dict) else {}
	if not isinstance(history_cfg, dict) or not history_cfg.get("enabled", True):
		return message

	max_ctx = int(history_cfg.get("context_messages", 12))
	if max_ctx <= 0 or not history:
		return message

	ctx = history[-max_ctx:]
	lines: List[str] = []
	for item in ctx:
		role = str(item.get("role", "")).strip().lower()
		content = str(item.get("content", "")).strip()
		if not content:
			continue
		if role == "assistant":
			lines.append(f"asistente: {content}")
		else:
			lines.append(f"usuario: {content}")

	if not lines:
		return message

	transcript = "\n".join(lines)
	return (
		"Contexto reciente de la conversacion (de mas antiguo a mas reciente):\n"
		f"{transcript}\n\n"
		"Mensaje actual del usuario:\n"
		f"{message}"
	)


def execute_tool_call(func_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
	try:
		svc_name, method_name = func_name.split("__", 1)
	except ValueError as exc:
		raise ValueError(f"Nombre de tool no válido: {func_name}") from exc

	svc = services.get(svc_name)
	if not svc:
		raise ValueError(f"Servicio {svc_name} no encontrado")

	logger.info("service call service=%s method=%s", svc_name, method_name)
	logger.debug("service call args service=%s method=%s args=%s", svc_name, method_name, args)

	method = svc.get_method(method_name)
	try:
		result = method(**args)
	except Exception:
		logger.exception("service call failed service=%s method=%s", svc_name, method_name)
		raise
	logger.debug("service call result service=%s method=%s result=%s", svc_name, method_name, result)
	return {
		"name": func_name,
		"content": json.dumps(result, default=str),
	}


def _extract_tool_user_message(tool_events: List[Dict[str, Any]]) -> Optional[str]:
	"""Return an optional user-facing message from the last successful tool event."""
	if not tool_events:
		return None

	last = tool_events[-1]
	result = last.get("result")
	if not isinstance(result, dict):
		return None
	if not result.get("ok"):
		return None

	user_message = result.get("user_message")
	if not isinstance(user_message, str):
		return None

	clean = user_message.strip()
	return clean or None


def init_engine():
	"""
	Carga dinámicamente un módulo desde ../engine/

	Args:
		module_name: nombre del módulo sin extensión .py

	Returns:
		El módulo cargado
	"""
	global config
	config_engine=config.get("engine")
	module_name=config_engine["module"]

	# get engine modules path
	current_dir = Path(__file__).parent
	engine_dir = current_dir.parent / "engine"
	module_path = engine_dir / f"{module_name}.py"
	if not module_path.exists():
		raise FileNotFoundError(f"No se encontró el módulo: {module_path}")

	# dynamic load module
	spec_name = f"aikit.engine.{module_name.replace('-', '_')}"
	spec = importlib.util.spec_from_file_location(spec_name, module_path)
	if spec is None or spec.loader is None:
		raise ImportError(f"No se pudo cargar el módulo desde: {module_path}")
	module = importlib.util.module_from_spec(spec)
	sys.modules[spec_name] = module
	spec.loader.exec_module(module)
	logger.info("engine module loaded module=%s path=%s", module_name, module_path)

	# Valida que el modulo cumple el contrato minimo del engine.
	validate_engine_contract(module)

	params = dict(config_engine.get("params", {}))
	# Política común: límite de pasos interno por engine, con valor por defecto.
	params.setdefault("max_steps", config_engine.get("max_steps", 6))
	if "prompt" not in params:
		prompt = build_engine_prompt(config_engine)
		if prompt:
			params["prompt"] = prompt
	#model="mistral:7b-instruct-v0.3-q4_K_M"
	#module.init(model=model)
	module.init(**params)

	global engine
	engine=module

@asynccontextmanager
async def init(app: FastAPI):
	"""
	FastAPI llamará automáticamente a esta función al arrancar y cerrar.
	"""

	try:
		# Read config (AIKIT_CONFIG permite usar configuraciones alternativas, p.ej. examples/)
		global config
		config_path = Path(os.getenv("AIKIT_CONFIG") or (Path(__file__).parent.parent / "aikit.yaml"))
		config=yaml.safe_load(config_path.read_text())
		setup_logging(config.get("log"))

		# Init engine
		init_engine()
		init_tools()
		global history_store
		history_store = build_history_store(config)
		logger.info("history store initialized backend=%s", config.get("history", {}).get("backend", "memory"))
		logger.info("aikit started")
	except Exception:
		logger.exception("Startup error while loading config/engine/services")
		raise

	#global engine
	#try:
	#	engine =
	#	print(f"engine inicializado: {engine_module}")
	#except Exception as e:
	#	print(f"Error al cargar engine: {e}")
	#	raise

	# Service running
	try:
		yield
	finally:
		logger.info("aikit stopped")

app = FastAPI(lifespan=init)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especifica los orígenes permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
	conversation_id: Optional[str] = None
	message: str


class ChatResponse(BaseModel):
	answer: str
	conversation_id: str
	principal_id: str


@app.get("/health")
async def health() -> Dict[str, Any]:
	"""Liveness probe: process is running."""
	return {
		"status": "ok",
		"service": "aikit",
	}


@app.get("/readiness")
async def readiness() -> Dict[str, Any]:
	"""Readiness probe: core dependencies are initialized."""
	issues: List[str] = []

	if not isinstance(config, dict) or not config:
		issues.append("config_not_loaded")

	if engine is None:
		issues.append("engine_not_initialized")

	if not services:
		issues.append("services_not_initialized")

	if not tools:
		issues.append("tools_not_initialized")

	if history_store is None:
		issues.append("history_store_not_initialized")

	if issues:
		raise HTTPException(
			status_code=503,
			detail={
				"status": "not_ready",
				"issues": issues,
			},
		)

	return {
		"status": "ready",
		"service": "aikit",
		"engine": getattr(engine, "__name__", "unknown"),
		"services": sorted(list(services.keys())),
		"tools_count": len(tools),
	}


@app.post("/session")
async def create_session(response: Response) -> Dict[str, Any]:
	"""Emite una sesión anónima firmada (modo cookie). El identificador lo genera el backend."""
	cookie_cfg, secret = build_session_config(config)
	if not secret:
		raise HTTPException(status_code=404, detail="Session mode not enabled")

	max_age = int(cookie_cfg.get("max_age_seconds", 86400) or 86400)
	principal_id = new_principal_id()
	token = issue_session_token(principal_id, secret, max_age)

	response.set_cookie(
		key=str(cookie_cfg.get("cookie_name", "aikit_session") or "aikit_session"),
		value=token,
		max_age=max_age,
		httponly=True,
		secure=bool(cookie_cfg.get("secure", False)),
		samesite=str(cookie_cfg.get("samesite", "lax") or "lax"),
	)
	# Se devuelve también en el cuerpo para clientes cross-origin que no puedan usar cookies.
	return {"principal_id": principal_id, "token": token, "expires_in": max_age}


@app.get("/conversations")
async def list_conversations(request: Request) -> Dict[str, Any]:
	if history_store is None:
		raise HTTPException(status_code=503, detail="History store not initialized")
	principal_id = resolve_principal(request, config)
	conversations = history_store.list_conversations(principal_id)
	return {"principal_id": principal_id, "conversation_ids": conversations}


@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, request: Request) -> Dict[str, Any]:
	if history_store is None:
		raise HTTPException(status_code=503, detail="History store not initialized")
	principal_id = resolve_principal(request, config)
	messages = history_store.get_messages(principal_id, conversation_id)
	return {
		"principal_id": principal_id,
		"conversation_id": conversation_id,
		"messages": messages,
	}

@app.post("/chat")
async def chat(req: ChatRequest, request: Request):
	if history_store is None:
		raise HTTPException(status_code=503, detail="History store not initialized")

	principal_id = resolve_principal(request, config)
	conv_id = (req.conversation_id or "default").strip() or "default"
	logger.debug("chat request conv_id=%s message=%s", conv_id, req.message)
	history = history_store.get_messages(principal_id, conv_id)
	message = apply_input_rewrites(req.message)
	effective_message = build_effective_message(message, history, config)
	tool_events: List[Dict[str, Any]] = []

	preferred_artist_query = ""
	artist_cmd_match = re.match(r"^\s*musica:\s*pon\s+(.+?)\s*$", message, flags=re.IGNORECASE)
	if artist_cmd_match:
		candidate_query = artist_cmd_match.group(1).strip()
		candidate_tokens = [tok for tok in re.split(r"\s+", candidate_query) if tok]
		music_service = services.get("music")
		artist_exists_fn = getattr(music_service, "_artist_exists", None)
		if len(candidate_tokens) >= 2 and callable(artist_exists_fn):
			try:
				if bool(artist_exists_fn(candidate_query)):
					preferred_artist_query = candidate_query
					logger.debug("artist-priority command detected query=%s", preferred_artist_query)
			except Exception:
				logger.exception("artist-priority detection failed query=%s", candidate_query)

	def execute_tool_call_with_capture(func_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
		effective_func_name = func_name
		effective_args = args

		if (
			preferred_artist_query
			and func_name == "music__play_track"
			and isinstance(args, dict)
			and not str(args.get("artist", "")).strip()
		):
			effective_func_name = "music__play_query"
			effective_args = {"query": preferred_artist_query}
			logger.debug(
				"artist-priority reroute from=%s args=%s to=%s args=%s",
				func_name,
				args,
				effective_func_name,
				effective_args,
			)

		tool_response = execute_tool_call(effective_func_name, effective_args)
		parsed_result: Any = {}
		if isinstance(tool_response.get("content"), str):
			try:
				parsed_result = json.loads(tool_response["content"])
			except Exception:
				parsed_result = {}
		tool_events.append({
			"func_name": effective_func_name,
			"args": effective_args,
			"result": parsed_result,
		})
		return tool_response
	#history = get_history(conv_id)

	# 1) Construimos el array de mensajes
	#messages: List[Dict[str, Any]] = []
	#messages.extend(history)
	#messages.append({"role": "user", "content": req.message})

	#tools = build_tools_from_services(services)
	#print(f"tools:\n{tools}")

	# 2) Agent loop
#	MAX_STEPS = 5
#	steps = 0
#	while True:
#		steps += 1
#		print(f"* STEP {steps}")
#		if steps > MAX_STEPS:
#			assistant_answer = "He realizado demasiados pasos internos y no puedo continuar."
#			messages.append({"role": "assistant", "content": assistant_answer})
#			save_history(conv_id, messages[len(history):])
#			return {"answer": assistant_answer, "conversation_id": conv_id}
#
#		# Llamada a la IA con tools activadas
#		response = client.chat.completions.create(
#			model=model,
#			messages=messages,
#			tools=tools,
#			tool_choice="auto",
#		)
#
#		msg = response.choices[0].message
#		print(f"msg={msg}")
#
#		# ¿Hay tool_calls?
#		tool_calls = getattr(msg, "tool_calls", None)
#
#		if tool_calls:
#			# Guardamos el mensaje "assistant" que pide usar herramientas
#			messages.append({
#				"role": "assistant",
#				"content": msg.content or "",
#				"tool_calls": [tc.to_dict() if hasattr(tc, "to_dict") else tc for tc in tool_calls],
#			})
#
#			# Ejecutar cada tool_call y añadir su resultado
#			for tc in tool_calls:
#				print(f"run tool {tc}")
#				tool_result = execute_tool_call(services, tc)
#
#				messages.append({
#					"role": "tool",
#					"tool_call_id": tool_result["tool_call_id"],
#					"name": tool_result["name"],
#					"content": tool_result["content"],
#				})
#
#			# siguiente iteración: la IA verá también los mensajes de tipo "tool"
#			continue
#
#		# Si no hay tool_calls, ya tenemos respuesta final para el usuario
#		assistant_answer = msg.content
#		messages.append({"role": "assistant", "content": assistant_answer})
#
#		# Guardar en el historial sólo lo nuevo (desde donde empezó esta petición)
#		save_history(conv_id, messages[len(history):])

	try:
		#answer="tienes razón"
		answer=engine.chat(effective_message, tools=tools, tool_executor=execute_tool_call_with_capture)
		tool_user_message = _extract_tool_user_message(tool_events)
		if tool_user_message:
			answer = tool_user_message
		logger.debug("chat response conv_id=%s answer=%s", conv_id, answer)
	except HTTPException:
		raise
	except Exception as exc:
		logger.exception("Chat error conv_id=%s message=%s", conv_id, message)
		raise HTTPException(
			status_code=502,
			detail=f"Engine error: {type(exc).__name__}: {exc}",
		)

	history_store.append_messages(
		principal_id,
		conv_id,
		[
			{"role": "user", "content": message},
			{"role": "assistant", "content": answer},
		],
	)

	return ChatResponse(answer=answer, conversation_id=conv_id, principal_id=principal_id).model_dump()
