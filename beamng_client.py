import requests
import json
import uuid


MCP_URL = "http://127.0.0.1:29292/mcp"


class BeamNGMCP:

    def __init__(self):

        self.session_id = None
        self.request_id = 0

        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }

        self.initialize()


    def initialize(self):

        self.request_id += 1

        payload = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {
                    "name": "beamng-research-client",
                    "version": "1.0"
                }
            }
        }

        response = requests.post(
            MCP_URL,
            headers=self.headers,
            json=payload,
            timeout=10
        )

        print("Initialize HTTP:", response.status_code)

        # Streamable HTTP MCP servers normally return
        # a session identifier in this header.
        self.session_id = response.headers.get(
            "Mcp-Session-Id"
        )

        if self.session_id:

            self.headers["Mcp-Session-Id"] = self.session_id

        print("MCP session:", self.session_id)


    def call(self, tool, arguments=None):

        self.request_id += 1

        payload = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "tools/call",
            "params": {
                "name": tool,
                "arguments": arguments or {}
            }
        }

        response = requests.post(
            MCP_URL,
            headers=self.headers,
            json=payload,
            timeout=30
        )

        print(
            f"{tool}: HTTP {response.status_code}"
        )

        return response.text