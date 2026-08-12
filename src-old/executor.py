# app/agent/executor.py
import json
from typing import Dict, Any, List
from services.service_contract import ServiceContract

def execute_tool_call(
    services: Dict[str, ServiceContract],
    tool_call: Any,
) -> Dict[str, Any]:
    """
    tool_call: un elemento de response.choices[0].message.tool_calls
    """
    func_name = tool_call.function.name          # p.ej. "stock__obtener_items"
    args_json = tool_call.function.arguments     # string JSON

    try:
        args = json.loads(args_json or "{}")
    except json.JSONDecodeError:
        args = {}

    # servicename__methodname
    try:
        svc_name, method_name = func_name.split("__", 1)
    except ValueError:
        raise ValueError(f"Nombre de herramienta no válido: {func_name}")

    svc = services.get(svc_name)
    if not svc:
        raise ValueError(f"Servicio {svc_name} no encontrado")

    method = svc.get_method(method_name)
    result = method(**args)

    # Devolvemos algo serializable
    return {
        "tool_call_id": tool_call.id,
        "name": func_name,
        "content": json.dumps(result, default=str),  # pydantic models -> dict
    }
