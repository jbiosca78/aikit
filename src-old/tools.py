# app/agent/tools.py
from typing import Dict, Any, List
from services.service_contract import ServiceContract

def build_tools_from_services(services: Dict[str, ServiceContract]) -> List[Dict[str, Any]]:
    tools = []
    for svc_name, svc in services.items():
        for m in svc.list_methods():
            tool_name = f"{svc_name}__{m.name}"  # p.ej. "stock__obtener_items"

            tool = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": f"[Servicio: {svc_name}] {m.description}",
                    "parameters": {
                        "type": "object",
                        "properties": m.params_schema,
                        "required": list(m.params_schema.keys()),
                    },
                },
            }
            tools.append(tool)
    return tools
