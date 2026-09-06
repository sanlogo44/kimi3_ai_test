"""
MCP-Protokoll (Model Context Protocol) für Tool-Aufrufe.
Definiert Server, Client, Tool-Definitionen und Ergebnisverarbeitung.
"""
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
import json
import asyncio


class MCPError(Exception):
    """Allgemeiner Fehler im MCP-Protokoll."""
    pass


@dataclass
class ToolParameter:
    """Beschreibt einen Parameter eines Werkzeugs."""
    name: str
    param_type: str
    description: str
    required: bool = True
    enum: Optional[List[str]] = None
    default: Any = None


@dataclass
class ToolDefinition:
    """Definiert ein Werkzeug mit Name, Beschreibung und Parametern."""
    name: str
    description: str
    parameters: List[ToolParameter]
    returns: Dict[str, Any] = field(default_factory=dict)

    def to_schema(self):
        """Erzeugt das JSON-Schema für dieses Werkzeug."""
        props, req = {}, []
        for p in self.parameters:
            prop = {"type": p.param_type, "description": p.description}
            if p.enum:
                prop["enum"] = p.enum
            if p.default is not None:
                prop["default"] = p.default
            props[p.name] = prop
            if p.required:
                req.append(p.name)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {"type": "object", "properties": props, "required": req}
            }
        }


@dataclass
class ToolCall:
    """Beschreibt einen einzelnen Werkzeugaufruf."""
    tool_name: str
    arguments: Dict[str, Any]
    call_id: str


@dataclass
class ToolResult:
    """Beschreibt das Ergebnis eines Werkzeugaufrufs."""
    call_id: str
    tool_name: str
    result: Any
    error: Optional[str] = None
    execution_time_ms: float = 0.0

    @property
    def erfolgreich(self) -> bool:
        """Meldet, ob der Aufruf ohne Fehler durchgelaufen ist."""
        return self.error is None

    #: Rückwärtskompatibler englischer Name
    success = erfolgreich


class MCPServer:
    """Server, der Werkzeuge registriert und ausführt."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._handlers: Dict[str, Callable] = {}

    def register_tool(self, definition: ToolDefinition, handler: Callable):
        """Registriert ein neues Werkzeug samt Implementierung."""
        self._tools[definition.name] = definition
        self._handlers[definition.name] = handler

    def get_tool_schemas(self):
        """Gibt die Schemas aller registrierten Werkzeuge zurück."""
        return [t.to_schema() for t in self._tools.values()]

    async def execute(self, call: ToolCall) -> ToolResult:
        """Führt einen Werkzeugaufruf asynchron aus."""
        start = asyncio.get_event_loop().time()
        if call.tool_name not in self._handlers:
            return ToolResult(call.call_id, call.tool_name, None,
                             f"Das Werkzeug „{call.tool_name}“ ist nicht bekannt.")
        try:
            h = self._handlers[call.tool_name]
            result = await h(**call.arguments) if asyncio.iscoroutinefunction(h) else h(**call.arguments)
            return ToolResult(call.call_id, call.tool_name, result, None,
                             (asyncio.get_event_loop().time() - start) * 1000)
        except Exception as e:
            return ToolResult(call.call_id, call.tool_name, None, str(e))


class MCPClient:
    """Client für die Kommunikation mit dem MCP-Server."""

    def __init__(self, server: MCPServer):
        self.server = server
        self.conversation_history: List[Dict] = []

    def get_system_prompt_with_tools(self):
        """Erzeugt die Systemanweisung samt Beschreibung aller Werkzeuge."""
        return f"""Du bist ein deutschsprachiger KI-Assistent mit Zugriff auf externe Werkzeuge.
Antworte immer auf Deutsch.

Verfügbare Werkzeuge:
{json.dumps(self.server.get_tool_schemas(), indent=2, ensure_ascii=False)}

Regeln:
1. Rufe ein Werkzeug auf, indem du ausschließlich JSON im Format {{"tool_call": {{"name": "...", "arguments": {{...}}}}}} ausgibst.
2. Ansonsten antworte normal als Text."""

    def parse_tool_call(self, text: str) -> Optional[ToolCall]:
        """Liest einen Werkzeugaufruf aus dem erzeugten Text, falls vorhanden."""
        try:
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0].strip()
            elif text.strip().startswith("{"):
                json_str = text.strip()
            elif "{\"tool_call\"" in text:
                # Auch eingebettetes JSON erkennen, etwa nach erklärendem Text.
                beginn = text.index("{\"tool_call\"")
                ende = text.rfind("}") + 1
                json_str = text[beginn:ende]
            else:
                return None
            data = json.loads(json_str)
            if isinstance(data, dict) and "tool_call" in data:
                tc = data["tool_call"] or {}
                name = tc.get("name")
                if not name:
                    return None
                argumente = tc.get("arguments") or {}
                if not isinstance(argumente, dict):
                    argumente = {}
                return ToolCall(name, argumente,
                               f"call_{len(self.conversation_history)}")
        except Exception:
            pass
        return None

    def formatiere_werkzeugaufruf(self, call: ToolCall) -> str:
        """Formatiert einen Werkzeug-Aufruf als gültiges JSON für den Verlauf."""
        return json.dumps(
            {"tool_call": {"name": call.tool_name, "arguments": call.arguments}},
            ensure_ascii=False,
        )

    def formatiere_werkzeugergebnis(self, result: ToolResult) -> str:
        """Formatiert das Werkzeugergebnis für den Gesprächsverlauf."""
        if result.error:
            return f"[WERKZEUG-FEHLER - {result.tool_name}]: {result.error}"
        inhalt = json.dumps(result.result, ensure_ascii=False)
        return f"[WERKZEUG-ERGEBNIS - {result.tool_name}]: {inhalt}"

    #: Rückwärtskompatibler englischer Name
    format_tool_result = formatiere_werkzeugergebnis
