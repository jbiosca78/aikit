#!/usr/bin/env python3

# ollama serve
# ollama pull llama3.1:8b
#


from typing import Dict, Any, List, Optional
import ast
import json
import logging
from openai import OpenAI


client = None
model_id = None
active_system_prompt = ""
active_max_steps = 6
logger = logging.getLogger("aikit.engine.ollama")


def init(
    model: str = "llama3.1:8b",
    url: str = "http://localhost:11434/v1",
    apikey: str = "ollama",
    prompt: Optional[str] = None,
    max_steps: int = 6,
    **kwargs,
):
    """
    Inicializa cliente OpenAI-compatible contra Ollama local.
    """
    global client, model_id, active_system_prompt, active_max_steps
    model_id = model
    active_system_prompt = (prompt or "").strip()
    active_max_steps = max(1, int(max_steps))
    client = OpenAI(base_url=url, api_key=apikey)
    logger.info("ollama client ready model=%s url=%s", model_id, url)


def _build_messages(user_message: str) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = []
    if active_system_prompt:
        messages.append({"role": "system", "content": active_system_prompt})
    messages.append({"role": "user", "content": user_message})
    return messages


def _parse_text_tool_call(content: str) -> Optional[Dict[str, Any]]:
    """
    Fallback para modelos que devuelven la llamada de tool como texto plano,
    por ejemplo: {'name': 'music__search_tracks', 'parameters': {'query': 'Enya'}}
    """
    text = (content or "").strip()
    if not text:
        return None

    parsed: Any = None
    try:
        parsed = json.loads(text)
    except Exception:
        try:
            parsed = ast.literal_eval(text)
        except Exception:
            return None

    if not isinstance(parsed, dict):
        return None

    name = parsed.get("name")
    params = parsed.get("parameters", {})
    if not isinstance(name, str) or not name.strip() or not isinstance(params, dict):
        return None

    return {"name": name.strip(), "parameters": params}


def chat(message, tools=None, tool_executor=None, **kwargs):
    global client, model_id, active_max_steps

    if client is None:
        raise RuntimeError("Motor Ollama no inicializado. Llama a init() primero.")

    messages = _build_messages(message)

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

        # Fallback: algunos modelos en Ollama no emiten tool_calls nativo y
        # devuelven una estructura textual con name/parameters.
        text_tool_call = _parse_text_tool_call(msg.content or "")
        if text_tool_call and callable(tool_executor):
            tool_name = text_tool_call["name"]
            tool_args = text_tool_call["parameters"]
            try:
                exec_result = tool_executor(tool_name, tool_args)
                tool_content = exec_result.get("content", "")
            except Exception as exc:
                logger.exception("textual tool execution failed tool=%s", tool_name)
                tool_content = f"Tool error: {exc}"

            messages.append({"role": "assistant", "content": msg.content or ""})
            messages.append({
                "role": "user",
                "content": (
                    "Tool executed successfully. "
                    f"Result for {tool_name}: {tool_content}. "
                    "Now answer the user in natural language."
                ),
            })
            continue

        return (msg.content or "").strip()

    return "No se pudo completar la respuesta tras varios pasos de herramientas."
