from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
import json
import asyncio

class MCPError(Exception): pass

@dataclass
class ToolParameter:
    name: str; param_type: str; description: str
    required: bool = True; enum: Optional[List[str]] = None; default: Any = None

@dataclass
class ToolDefinition:
    name: str; description: str; parameters: List[ToolParameter]
    returns: Dict[str, Any] = field(default_factory=dict)
    def to_schema(self):
        props, req = {}, []
        for p in self.parameters:
            prop = {"type": p.param_type, "description": p.description}
            if p.enum: prop["enum"] = p.enum
            if p.default is not None: prop["default"] = p.default
            props[p.name] = prop
            if p.required: req.append(p.name)
        return {"type": "function", "function": {"name": self.name, "description": self.description,
                "parameters": {"type": "object", "properties": props, "required": req}}}

@dataclass
class ToolCall:
    tool_name: str; arguments: Dict[str, Any]; call_id: str

@dataclass
class ToolResult:
    call_id: str; tool_name: str; result: Any; error: Optional[str] = None; execution_time_ms: float = 0.0

class MCPServer:
    def __init__(self): self._tools: Dict[str, ToolDefinition] = {}; self._handlers: Dict[str, Callable] = {}
    def register_tool(self, definition: ToolDefinition, handler: Callable):
        self._tools[definition.name] = definition; self._handlers[definition.name] = handler
    def get_tool_schemas(self): return [t.to_schema() for t in self._tools.values()]
    async def execute(self, call: ToolCall) -> ToolResult:
        start = asyncio.get_event_loop().time()
        if call.tool_name not in self._handlers:
            return ToolResult(call.call_id, call.tool_name, None, f"Tool '{call.tool_name}' nicht gefunden")
        try:
            h = self._handlers[call.tool_name]
            result = await h(**call.arguments) if asyncio.iscoroutinefunction(h) else h(**call.arguments)
            return ToolResult(call.call_id, call.tool_name, result, None, (asyncio.get_event_loop().time()-start)*1000)
        except Exception as e:
            return ToolResult(call.call_id, call.tool_name, None, str(e))

class MCPClient:
    def __init__(self, server: MCPServer): self.server = server; self.conversation_history: List[Dict] = []
    def get_system_prompt_with_tools(self):
        return f"""Du bist ein KI-Assistent mit Tools.\nVerfügbar:\n{json.dumps(self.server.get_tool_schemas(), indent=2, ensure_ascii=False)}\n\nRegeln:\n1. Tool-Call als JSON: {{\"tool_call\": {{\"name\": \"...\", \"arguments\": {{...}}}}}}\n2. Sonst normaler Text."""
    def parse_tool_call(self, text: str) -> Optional[ToolCall]:
        try:
            if "```json" in text: json_str = text.split("```json")[1].split("```")[0].strip()
            elif text.strip().startswith("{"): json_str = text.strip()
            else: return None
            data = json.loads(json_str)
            if "tool_call" in data:
                tc = data["tool_call"]
                return ToolCall(tc["name"], tc["arguments"], f"call_{len(self.conversation_history)}")
        except: pass
        return None
    def format_tool_result(self, result: ToolResult):
        if result.error: return f"[TOOL ERROR - {result.tool_name}]: {result.error}"
        return f"[TOOL RESULT - {result.tool_name}]: {json.dumps(result.result, ensure_ascii=False)}"