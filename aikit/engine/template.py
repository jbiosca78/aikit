#!/usr/bin/env python3

from openai import OpenAI
from typing import Dict, Any, Optional, List

# Variables globales
client = None
model_id = None
active_system_prompt = ""
active_max_steps = 6

def init(url="", apikey="", model="", prompt: Optional[str] = None, max_steps: int = 6, **kwargs):
	global client, model_id, active_system_prompt, active_max_steps
	model_id = model
	active_system_prompt = (prompt or "").strip()
	active_max_steps = max(1, int(max_steps))
	client = OpenAI(base_url=url, api_key=apikey)

def chat(message, tools=None, tool_executor=None, **kwargs):
	global client, model_id, active_system_prompt, active_max_steps

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
				try:
					import json
					tool_args = json.loads(tc.function.arguments or "{}")
				except Exception:
					tool_args = {}
				exec_result = tool_executor(tc.function.name, tool_args)
				messages.append({
					"role": "tool",
					"tool_call_id": tc.id,
					"content": str(exec_result.get("content", "")),
				})
			continue
		return (msg.content or "").strip()

	return "No se pudo completar la respuesta tras varios pasos de herramientas."
