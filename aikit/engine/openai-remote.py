#!/usr/bin/env python3

from openai import OpenAI
from typing import Dict, Any, Optional, List
import logging

# Variables globales
client = None
model_id = None
active_system_prompt = ""
active_max_steps = 6
logger = logging.getLogger("aikit.engine.openai_remote")

def init(url, apikey, model, prompt: Optional[str] = None, max_steps: int = 6, **kwargs):
	global client, model_id, active_system_prompt, active_max_steps
	model_id = model
	active_system_prompt = (prompt or "").strip()
	active_max_steps = max(1, int(max_steps))
	client = OpenAI(base_url=url, api_key=apikey)
	logger.info("openai remote client ready model=%s url=%s", model_id, url)

def chat(message, tools=None, tool_executor=None, **kwargs):
	global client, model_id, active_system_prompt, active_max_steps
	if client is None:
		raise RuntimeError("Motor OpenAI remoto no inicializado. Llama a init() primero.")

	messages: List[Dict[str, Any]] = []
	if active_system_prompt:
		messages.append({"role": "system", "content": active_system_prompt})
	messages.append({"role": "user", "content": message})

	for _ in range(active_max_steps):
		request: Dict[str, Any] = {
			"model": model_id,
			"messages": messages,
		}
		if tools:
			request["tools"] = tools
			request["tool_choice"] = "auto"
		logger.debug("openai remote request model=%s tools_enabled=%s", model_id, bool(tools))

		response = client.chat.completions.create(**request)
		msg = response.choices[0].message
		tool_calls = getattr(msg, "tool_calls", None) or []
		if tool_calls and callable(tool_executor):
			messages.append({
				"role": "assistant",
				"content": msg.content or "",
				"tool_calls": [tc.model_dump() for tc in tool_calls],
			})

			for tc in tool_calls:
				tool_name = tc.function.name
				raw_args = tc.function.arguments or "{}"
				try:
					import json
					tool_args = json.loads(raw_args)
				except Exception:
					tool_args = {}

				try:
					exec_result = tool_executor(tool_name, tool_args)
					tool_content = exec_result.get("content", "")
				except Exception as exc:
					logger.exception("tool execution failed tool=%s", tool_name)
					tool_content = f"Tool error: {exc}"

				messages.append({
					"role": "tool",
					"tool_call_id": tc.id,
					"content": str(tool_content),
				})
			continue

		return (msg.content or "").strip()

	return "No se pudo completar la respuesta tras varios pasos de herramientas."
