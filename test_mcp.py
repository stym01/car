import requests
import json

URL = "http://127.0.0.1:29292/mcp"

headers = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
}

r = requests.post(
    URL,
    headers=headers,
    json=payload,
    timeout=10
)

print("\n==============================")
print("BeamNG MCP TOOLS")
print("==============================\n")

print(r.text)