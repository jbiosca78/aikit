"""Asistente de catálogo implementado con LangChain, sin AiKit.

Cuarta variante del estudio comparativo. LangChain resuelve la orquestacion y la invocacion
de herramientas; la identidad, la persistencia del historial y el servicio web siguen siendo
responsabilidad del integrador.
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

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

import catalogo

MODEL_ID = os.getenv("LC_MODEL", "eu.amazon.nova-lite-v1:0")
AWS_PROFILE = os.getenv("LC_AWS_PROFILE", "aikit")
HISTORY_PATH = Path(os.getenv("LC_HISTORY", "history.json"))
SESSION_SECRET = os.getenv("LC_SESSION_SECRET", "")
SESSION_MAX_AGE = 86400
CONTEXT_MESSAGES = 12
MAX_MESSAGES = 200

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


# --- herramientas -----------------------------------------------------------
# LangChain deriva el esquema de la firma y del docstring de cada funcion.

@tool
def list_models() -> List[Dict[str, Any]]:
	"""Devuelve un resumen de todos los modelos del catálogo."""
	return catalogo.list_models()


@tool
def get_model(model: str) -> Dict[str, Any]:
	"""Devuelve todos los datos de un modelo del catálogo por identificador o nombre."""
	return catalogo.get_model(model)


@tool
def search_models(
	text: str = "",
	color: str = "",
	max_price: Optional[float] = None,
	max_width_cm: Optional[float] = None,
	max_height_cm: Optional[float] = None,
	max_depth_cm: Optional[float] = None,
	only_available: bool = False,
) -> List[Dict[str, Any]]:
	"""Busca modelos del catálogo por texto libre, color, precio máximo o medidas maximas."""
	return catalogo.search_models(
		text=text,
		color=color,
		max_price=max_price,
		max_width_cm=max_width_cm,
		max_height_cm=max_height_cm,
		max_depth_cm=max_depth_cm,
		only_available=only_available,
	)


@tool
def compare_models(model_a: str, model_b: str) -> Dict[str, Any]:
	"""Compara dos modelos del catálogo campo a campo."""
	return catalogo.compare_models(model_a, model_b)


@tool
def check_availability(model: str) -> Dict[str, Any]:
	"""Devuelve stock, disponibilidad y plazo de envío de un modelo."""
	return catalogo.check_availability(model)


TOOLS = [list_models, get_model, search_models, compare_models, check_availability]

llm = ChatBedrockConverse(model=MODEL_ID, credentials_profile_name=AWS_PROFILE)
agent = create_react_agent(llm, TOOLS)


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


def to_langchain_messages(history: List[Dict[str, str]]) -> List[Any]:
	mensajes: List[Any] = [SystemMessage(content=SYSTEM_PROMPT)]
	for m in history[-CONTEXT_MESSAGES:]:
		if m["role"] == "user":
			mensajes.append(HumanMessage(content=m["content"]))
		else:
			mensajes.append(AIMessage(content=m["content"]))
	return mensajes


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
		raise HTTPException(status_code=500, detail="LC_SESSION_SECRET no configurado")
	principal_id = f"web-{uuid.uuid4().hex}"
	token = issue_token(principal_id)
	response.set_cookie("session", token, max_age=SESSION_MAX_AGE, httponly=True, samesite="strict")
	return {"principal_id": principal_id, "token": token, "expires_in": SESSION_MAX_AGE}


@app.post("/chat")
async def chat(req: ChatRequest, request: Request) -> Dict[str, str]:
	principal = resolve_principal(request)
	conversation = (req.conversation_id or "default").strip() or "default"

	history = get_messages(principal, conversation)
	mensajes = to_langchain_messages(history)
	mensajes.append(HumanMessage(content=req.message))

	resultado = agent.invoke({"messages": mensajes})
	answer = resultado["messages"][-1].content
	if isinstance(answer, list):
		answer = "".join(bloque.get("text", "") for bloque in answer if isinstance(bloque, dict))

	append_messages(principal, conversation, [
		{"role": "user", "content": req.message},
		{"role": "assistant", "content": answer},
	])
	return {"answer": answer, "conversation_id": conversation, "principal_id": principal}
