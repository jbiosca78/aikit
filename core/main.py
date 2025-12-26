#!/usr/bin/env python3

# app/main.py
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
#from openai import OpenAI
from pathlib import Path
import yaml
import importlib
import inspect

#from tools import build_tools_from_services
#from executor import execute_tool_call
#from services.base import BaseService
from contextlib import asynccontextmanager

conversation_store: Dict[str, List[Dict]] = {} # historial por conversation_id

@asynccontextmanager
async def startup(app: FastAPI):
	"""
	FastAPI llamará automáticamente a esta función al arrancar y cerrar.
	"""
	# Startup
	#load_services()
	print("Startup")
	yield
	# Shutdown (si necesitas hacer limpieza)

app = FastAPI(lifespan=startup)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especifica los orígenes permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ejemplo opcional: endpoint para llamar un método directamente (útil mientras montas la IA)
from pydantic import BaseModel
from typing import Any, Dict

def get_history(conv_id: Optional[str]) -> List[Dict[str, Any]]:
	if not conv_id:
		return []
	return conversation_store.setdefault(conv_id, [])

def save_history(conv_id: Optional[str], messages: List[Dict[str, Any]]):
	if not conv_id:
		return
	conversation_store.setdefault(conv_id, []).extend(messages)

class ChatRequest(BaseModel):
	conversation_id: Optional[str] = None
	message: str

@app.post("/chat")
async def chat(req: ChatRequest):
	conv_id = req.conversation_id or "anon"
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

	answer="tienes razón"

	return {
		"answer": answer
		#"conversation_id": conv_id,
	}


if __name__ == "__main__":
	import uvicorn
	uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
