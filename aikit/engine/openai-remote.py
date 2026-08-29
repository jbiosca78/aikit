#!/usr/bin/env python3

from openai import OpenAI
from typing import Dict, Any, Optional, List
import logging

# Variables globales
client = None
model_id = None
logger = logging.getLogger("aikit.engine.openai_remote")

def init(url, apikey, model, **kwargs):
	global client, model_id
	model_id = model
	client = OpenAI(base_url=url, api_key=apikey)
	logger.info("openai remote client ready model=%s url=%s", model_id, url)

def chat(message, tools=None, tool_executor=None, **kwargs):
	global client, model_id
	if client is None:
		raise RuntimeError("Motor OpenAI remoto no inicializado. Llama a init() primero.")

	messages: List[Dict[str, Any]] = []
	#messages.extend(history)
	messages.append({"role": "user", "content": message})

	# Llamada a la IA con tools activadas
	request: Dict[str, Any] = {
		"model": model_id,
		"messages": messages,
	}
	if tools:
		request["tools"] = tools
		request["tool_choice"] = "auto"
	logger.debug("openai remote request model=%s tools_enabled=%s", model_id, bool(tools))

	response = client.chat.completions.create(**request)

	return response.choices[0].message.content
