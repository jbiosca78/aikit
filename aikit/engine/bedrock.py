#!/usr/bin/env python3

# requisites:
# pip install boto3

import boto3
from typing import Dict, Any, List, Optional
import re
import logging
from botocore.exceptions import ClientError

# Variables globales
client = None
model_id = None
active_system_prompt = ""
active_max_steps = 6
logger = logging.getLogger("aikit.engine.bedrock")

def init(
	model: str = "amazon.nova-lite-v1:0",
	aws_profile: Optional[str] = None,
	region: Optional[str] = None,
	aws_access_key_id: Optional[str] = None,
	aws_secret_access_key: Optional[str] = None,
	prompt: Optional[str] = None,
	max_steps: int = 6,
):
	"""
	Inicializa el cliente de AWS Bedrock Runtime.

	Credenciales: si no se pasan explícitamente se usan las credenciales
	estándar de boto3 (variables de entorno, ~/.aws/credentials, IAM role...).
	Si se pasa `aws_profile`, se usa el perfil de AWS correspondiente (por ejemplo,
	en ~/.aws/config y ~/.aws/credentials).
	Región: si se pasa `region`, tiene prioridad. Si no se pasa, boto3 usa la
	región del profile o de la configuración por defecto de AWS.

	Modelos habituales:
		amazon.nova-lite-v1:0
		amazon.nova-pro-v1:0
		anthropic.claude-3-5-sonnet-20241022-v2:0
		anthropic.claude-3-haiku-20240307-v1:0
		meta.llama3-1-8b-instruct-v1:0
		mistral.mistral-large-2402-v1:0
	"""
	global client, model_id, active_system_prompt, active_max_steps
	model_id = model
	active_system_prompt = (prompt or "").strip()
	active_max_steps = max(1, int(max_steps))
	session_kwargs: Dict[str, Any] = {}
	if region:
		session_kwargs["region_name"] = region
	if aws_profile:
		session_kwargs["profile_name"] = aws_profile
	if aws_access_key_id:
		session_kwargs["aws_access_key_id"] = aws_access_key_id
	if aws_secret_access_key:
		session_kwargs["aws_secret_access_key"] = aws_secret_access_key

	session = boto3.Session(**session_kwargs)
	client = session.client("bedrock-runtime")
	effective_region = session.region_name or region or "<sin-region>"
	profile_info = f", profile: {aws_profile}" if aws_profile else ""
	logger.info("bedrock client ready model=%s region=%s%s", model_id, effective_region, profile_info)


def _map_tools_to_bedrock(tools: List[Dict[str, Any]]) -> Dict[str, Any]:
	tool_specs: List[Dict[str, Any]] = []
	for t in tools:
		fn = t.get("function", {})
		name = fn.get("name")
		if not name:
			continue
		tool_specs.append({
			"toolSpec": {
				"name": name,
				"description": fn.get("description", ""),
				"inputSchema": {
					"json": fn.get("parameters", {"type": "object", "properties": {}}),
				},
			}
		})
	return {"tools": tool_specs}


def _clean_answer(text: str) -> str:
	# Evita exponer razonamiento interno si el modelo devuelve bloques thinking.
	cleaned = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL | re.IGNORECASE)
	# Quita etiquetas de wrapper genéricas que algunos modelos añaden.
	cleaned = re.sub(r"<response>\s*", "", cleaned, flags=re.IGNORECASE)
	cleaned = re.sub(r"\s*</response>", "", cleaned, flags=re.IGNORECASE)
	# Quita prefacios meta redundantes.
	cleaned = re.sub(
		r"^\s*(gracias a la información obtenida[,.:;\s-]*)",
		"",
		cleaned,
		flags=re.IGNORECASE,
	)
	cleaned = re.sub(
		r"^\s*(según la información obtenida[,.:;\s-]*)",
		"",
		cleaned,
		flags=re.IGNORECASE,
	)
	# Evita formulaciones en primera persona no deseadas.
	cleaned = re.sub(r"\bte he pedido que\b", "has pedido que", cleaned, flags=re.IGNORECASE)
	cleaned = re.sub(r"\bhe pedido que\b", "has pedido que", cleaned, flags=re.IGNORECASE)
	return cleaned.strip()


def _looks_like_tool_denial(text: str) -> bool:
	normalized = (text or "").strip().lower()
	if not normalized:
		return False
	denial_markers = [
		"no tengo herramientas",
		"no dispongo de herramientas",
		"no puedo usar herramientas",
		"i don't have tools",
		"i do not have tools",
		"i cannot use tools",
	]
	return any(marker in normalized for marker in denial_markers)


def chat(message: str, tools: Optional[List[Dict[str, Any]]] = None, tool_executor=None, **kwargs) -> str:
	"""
	Envía un mensaje al modelo usando la API Converse de Bedrock y
	devuelve el texto de la respuesta.
	"""
	global client, model_id

	if client is None:
		raise RuntimeError("Motor Bedrock no inicializado. Llama a init() primero.")

	messages: List[Dict[str, Any]] = [
		{"role": "user", "content": [{"text": message}]}
	]
	last_tool_result_text = ""
	forced_tool_retry_done = False

	max_steps = active_max_steps
	for step in range(max_steps):
		request: Dict[str, Any] = {
			"modelId": model_id,
			"messages": messages,
		}
		if active_system_prompt:
			request["system"] = [{"text": active_system_prompt}]
		if tools:
			request["toolConfig"] = _map_tools_to_bedrock(tools)

		try:
			response = client.converse(**request)
		except ClientError as exc:
			error_code = exc.response.get("Error", {}).get("Code", "")
			if error_code == "InvalidSignatureException":
				raise RuntimeError(
					"AWS firma invalida (InvalidSignatureException). Revisa region/model/profile y credenciales. "
					f"model={model_id}, client_region={getattr(client.meta, 'region_name', '<unknown>')}"
				) from exc
			raise
		out_message = response["output"]["message"]
		blocks = out_message.get("content", [])

		text_parts: List[str] = []
		tool_uses: List[Dict[str, Any]] = []
		for block in blocks:
			if "text" in block:
				text_parts.append(block["text"])
			if "toolUse" in block:
				tool_uses.append(block["toolUse"])

		# Si el modelo solicita tools y tenemos ejecutor, resolvemos y continuamos.
		if tool_uses and callable(tool_executor):
			messages.append({"role": "assistant", "content": blocks})

			tool_result_blocks: List[Dict[str, Any]] = []
			for tu in tool_uses:
				tool_name = tu.get("name", "")
				tool_args = tu.get("input", {}) or {}
				tool_use_id = tu.get("toolUseId", "")
				try:
					exec_result = tool_executor(tool_name, tool_args)
					result_text = exec_result.get("content", "")
					status = "success"
				except Exception as exc:
					result_text = f"Tool error: {exc}"
					status = "error"
				last_tool_result_text = result_text or last_tool_result_text

				tool_result_blocks.append({
					"toolResult": {
						"toolUseId": tool_use_id,
						"status": status,
						"content": [{"text": result_text}],
					}
				})

			messages.append({"role": "user", "content": tool_result_blocks})
			continue

		final_text = "\n".join([t for t in text_parts if t]).strip()
		cleaned_final = _clean_answer(final_text)
		if cleaned_final:
			# Algunos modelos responden por error que no tienen tools aunque sí las tengan.
			if (
				tools
				and callable(tool_executor)
				and not forced_tool_retry_done
				and _looks_like_tool_denial(cleaned_final)
				and step < (max_steps - 1)
			):
				forced_tool_retry_done = True
				messages.append({
					"role": "user",
					"content": [{
						"text": (
							"Sí tienes herramientas disponibles. "
							"Usa la herramienta más adecuada para resolver la petición "
							"del usuario y después responde con el resultado."
						)
					}],
				})
				continue
			return cleaned_final

		# Algunos modelos pueden cerrar el turno sin texto tras usar tools.
		# Forzamos un intento extra de respuesta al usuario antes de rendirnos.
		if last_tool_result_text and step < (max_steps - 1):
			messages.append({
				"role": "user",
				"content": [{
					"text": (
						"Con los resultados de herramientas ya disponibles, responde "
						"ahora al usuario en lenguaje natural y no llames más herramientas."
					)
				}],
			})
			continue

		if last_tool_result_text:
			return _clean_answer(str(last_tool_result_text))

		return "No he podido generar una respuesta final."

	return "No se pudo completar la respuesta tras varios pasos de herramientas."
