"""Asistente de catálogo implementado directamente sobre el SDK del proveedor, sin framework.

Sirve como linea base para medir el esfuerzo de integracion frente a la version con aikit.
"""

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import catalogo

MODEL_ID = os.getenv("BASELINE_MODEL", "eu.amazon.nova-lite-v1:0")
AWS_PROFILE = os.getenv("BASELINE_AWS_PROFILE", "aikit")
HISTORY_PATH = Path(os.getenv("BASELINE_HISTORY", "history.json"))
SESSION_SECRET = os.getenv("BASELINE_SESSION_SECRET", "")
SESSION_MAX_AGE = 86400
CONTEXT_MESSAGES = 12
MAX_MESSAGES = 200
MAX_STEPS = 6

SYSTEM_PROMPT = "\n".join([
	"Eres el asistente comercial de Armarios Mario, una tienda de armarios a medida.",
	"Responde solo con datos obtenidos del catálogo mediante las herramientas disponibles.",
	"Si un dato no esta en el catálogo, dilo claramente y ofrece contactar con la tienda.",
	"Habla en segunda persona, en español, de forma cercana y profesional.",
	"Se breve por defecto: 1-3 frases salvo que el usuario pida comparativas o detalle.",
	"Da los precios en euros y las medidas en centimetros, indicando siempre el modelo.",
	"No menciones herramientas, funciones ni pasos internos de razonamiento.",
	"No inventes promociones, descuentos, plazos ni modelos que no aparezcan en el catálogo.",
])

# Esquemas de las herramientas en el formato que espera el proveedor.
TOOLS: List[Dict[str, Any]] = [
	{
		"toolSpec": {
			"name": "list_models",
			"description": "Devuelve un resumen de todos los modelos del catálogo.",
			"inputSchema": {"json": {"type": "object", "properties": {}, "required": []}},
		}
	},
	{
		"toolSpec": {
			"name": "get_model",
			"description": "Devuelve todos los datos de un modelo por id o nombre.",
			"inputSchema": {"json": {
				"type": "object",
				"properties": {"model": {"type": "string", "description": "Identificador o nombre."}},
				"required": ["model"],
			}},
		}
	},
	{
		"toolSpec": {
			"name": "search_models",
			"description": "Busca modelos por precio, medidas, color o texto libre.",
			"inputSchema": {"json": {
				"type": "object",
				"properties": {
					"text": {"type": "string", "description": "Texto libre."},
					"color": {"type": "string", "description": "Color deseado."},
					"max_price": {"type": "number", "description": "Precio máximo en euros."},
					"max_width_cm": {"type": "number", "description": "Ancho máximo en cm."},
					"max_height_cm": {"type": "number", "description": "Alto máximo en cm."},
					"max_depth_cm": {"type": "number", "description": "Fondo máximo en cm."},
					"only_available": {"type": "boolean", "description": "Solo con stock."},
				},
				"required": [],
			}},
		}
	},
	{
		"toolSpec": {
			"name": "compare_models",
			"description": "Compara dos modelos campo a campo.",
			"inputSchema": {"json": {
				"type": "object",
				"properties": {
					"model_a": {"type": "string", "description": "Primer modelo."},
					"model_b": {"type": "string", "description": "Segundo modelo."},
				},
				"required": ["model_a", "model_b"],
			}},
		}
	},
	{
		"toolSpec": {
			"name": "check_availability",
			"description": "Devuelve stock, disponibilidad y plazo de envío de un modelo.",
			"inputSchema": {"json": {
				"type": "object",
				"properties": {"model": {"type": "string", "description": "Identificador o nombre."}},
				"required": ["model"],
			}},
		}
	},
]

DISPATCH = {
	"list_models": catalogo.list_models,
	"get_model": catalogo.get_model,
	"search_models": catalogo.search_models,
	"compare_models": catalogo.compare_models,
	"check_availability": catalogo.check_availability,
}

client = boto3.Session(profile_name=AWS_PROFILE).client("bedrock-runtime")


# --- sesion firmada ---------------------------------------------------------

def _b64e(raw: bytes) -> str:
	return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(value: str) -> bytes:
	return base64.urlsafe_b64decode(value + "=" * ((4 - len(value) % 4) % 4))


def issue_token(principal_id: str) -> str:
	payload = json.dumps(
		{"sub": principal_id, "exp": int(time.time()) + SESSION_MAX_AGE},
		separators=(",", ":"),
	).encode("utf-8")
	encoded = _b64e(payload)
	signature = hmac.new(SESSION_SECRET.encode(), encoded.encode(), hashlib.sha256).digest()
	return f"{encoded}.{_b64e(signature)}"


def verify_token(token: str) -> Optional[str]:
	parts = token.split(".")
	if len(parts) != 2:
		return None
	encoded, signature = parts
	try:
		expected = hmac.new(SESSION_SECRET.encode(), encoded.encode(), hashlib.sha256).digest()
		if not hmac.compare_digest(_b64d(signature), expected):
			return None
		payload = json.loads(_b64d(encoded).decode("utf-8"))
	except Exception:
		return None
	if not isinstance(payload.get("exp"), (int, float)) or time.time() > payload["exp"]:
		return None
	sub = payload.get("sub")
	return sub if isinstance(sub, str) and sub else None


def resolve_principal(request: Request) -> str:
	token = request.cookies.get("session") or request.headers.get("x-session-token", "")
	if token:
		sub = verify_token(token)
		if sub:
			return sub
	return "anon"


# --- historial --------------------------------------------------------------

def read_history() -> Dict[str, Dict[str, List[Dict[str, str]]]]:
	if not HISTORY_PATH.exists():
		return {}
	try:
		return json.loads(HISTORY_PATH.read_text(encoding="utf-8")) or {}
	except (json.JSONDecodeError, OSError):
		return {}


def write_history(data: Dict[str, Dict[str, List[Dict[str, str]]]]) -> None:
	HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
	HISTORY_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_messages(principal: str, conversation: str) -> List[Dict[str, str]]:
	return read_history().get(principal, {}).get(conversation, [])


def append_messages(principal: str, conversation: str, messages: List[Dict[str, str]]) -> None:
	data = read_history()
	conversations = data.setdefault(principal, {})
	stored = conversations.setdefault(conversation, [])
	stored.extend(messages)
	conversations[conversation] = stored[-MAX_MESSAGES:]
	write_history(data)


def build_message(message: str, history: List[Dict[str, str]]) -> str:
	if not history:
		return message
	recent = history[-CONTEXT_MESSAGES:]
	lines = [f"{m['role']}: {m['content']}" for m in recent]
	return "Historial reciente:\n" + "\n".join(lines) + f"\n\nMensaje actual:\n{message}"


# --- bucle de invocacion de herramientas ------------------------------------

def execute_tool(name: str, args: Dict[str, Any]) -> str:
	fn = DISPATCH.get(name)
	if fn is None:
		return json.dumps({"error": f"herramienta desconocida: {name}"})
	try:
		return json.dumps(fn(**args), ensure_ascii=False, default=str)
	except Exception as exc:
		return json.dumps({"error": str(exc)})


def chat_with_model(message: str) -> str:
	messages: List[Dict[str, Any]] = [{"role": "user", "content": [{"text": message}]}]

	for _ in range(MAX_STEPS):
		try:
			response = client.converse(
				modelId=MODEL_ID,
				messages=messages,
				system=[{"text": SYSTEM_PROMPT}],
				toolConfig={"tools": TOOLS},
			)
		except ClientError as exc:
			raise HTTPException(status_code=502, detail=f"error del proveedor: {exc}") from exc

		blocks = response["output"]["message"].get("content", [])
		texts = [b["text"] for b in blocks if "text" in b]
		tool_uses = [b["toolUse"] for b in blocks if "toolUse" in b]

		if not tool_uses:
			answer = "\n".join(t for t in texts if t).strip()
			return answer or "No he podido generar una respuesta."

		messages.append({"role": "assistant", "content": blocks})
		results = []
		for use in tool_uses:
			results.append({
				"toolResult": {
					"toolUseId": use.get("toolUseId", ""),
					"status": "success",
					"content": [{"text": execute_tool(use.get("name", ""), use.get("input") or {})}],
				}
			})
		messages.append({"role": "user", "content": results})

	return "No se pudo completar la respuesta tras varios pasos."


# --- API --------------------------------------------------------------------

app = FastAPI()
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


class ChatRequest(BaseModel):
	conversation_id: Optional[str] = None
	message: str


@app.get("/health")
async def health() -> Dict[str, str]:
	return {"status": "ok"}


@app.post("/session")
async def create_session(response: Response) -> Dict[str, Any]:
	if not SESSION_SECRET:
		raise HTTPException(status_code=500, detail="BASELINE_SESSION_SECRET no configurado")
	principal_id = f"web-{uuid.uuid4().hex}"
	token = issue_token(principal_id)
	response.set_cookie("session", token, max_age=SESSION_MAX_AGE, httponly=True, samesite="strict")
	return {"principal_id": principal_id, "token": token, "expires_in": SESSION_MAX_AGE}


@app.post("/chat")
async def chat(req: ChatRequest, request: Request) -> Dict[str, str]:
	principal = resolve_principal(request)
	conversation = (req.conversation_id or "default").strip() or "default"

	history = get_messages(principal, conversation)
	answer = chat_with_model(build_message(req.message, history))

	append_messages(principal, conversation, [
		{"role": "user", "content": req.message},
		{"role": "assistant", "content": answer},
	])
	return {"answer": answer, "conversation_id": conversation, "principal_id": principal}
