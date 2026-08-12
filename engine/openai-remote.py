#!/usr/bin/env python3

from openai import OpenAI
from typing import Dict, Any, Optional, List

# Variables globales
client = None
model_id = None

def init(url, apikey, model, **kwargs):
	global client, model_id
	model_id = model
	client = OpenAI(base_url=url, api_key=apikey)

def chat(message, tools=None, tool_executor=None, **kwargs):
	global client, model_id

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

	response = client.chat.completions.create(**request)

	return response.choices[0].message.content
