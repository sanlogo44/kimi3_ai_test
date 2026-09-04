import datetime, random
from mcp_protocol import MCPServer, ToolDefinition, ToolParameter

def create_math_tools() -> MCPServer:
    s = MCPServer()
    s.register_tool(ToolDefinition("calculator", "Rechnet", [ToolParameter("expression","string","z.B. 2+2")]),
        lambda e: eval(e, {"__builtins__":{}}, {"sqrt":lambda x:x**0.5,"pow":pow,"abs":abs,"round":round,"max":max,"min":min}))
    s.register_tool(ToolDefinition("get_weather", "Wetterdaten", [
        ToolParameter("location","string","Stadt"),
        ToolParameter("unit","string","Einheit",False,["celsius","fahrenheit"],"celsius")]),
        lambda loc,unit="celsius": {"location":loc,"temperature":random.randint(15,28) if unit=="celsius" else random.randint(59,82),
         "unit":unit,"condition":random.choice(["Sonnig","Bewölkt","Leichter Regen"]),"humidity":random.randint(40,80)})
    s.register_tool(ToolDefinition("web_search", "Internetsuche", [
        ToolParameter("query","string","Suchbegriff"), ToolParameter("num_results","number","Anzahl",False,default=3)]),
        lambda q,n=3: {"query":q,"results":[{"title":f"Ergebnis {i+1} für '{q}'","url":f"https://example.com/{i}","snippet":f"Text..."} for i in range(int(n))]})
    s.register_tool(ToolDefinition("get_current_time", "Aktuelle Zeit", []),
        lambda: {"datetime":datetime.datetime.now().isoformat(),"timezone":"UTC"})
    return s