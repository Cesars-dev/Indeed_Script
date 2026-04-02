#!/usr/bin/env python3
"""
Supabase MCP stdio server — wraps the PostgREST API as MCP tools.

No personal access token needed — uses SUPABASE_URL + SUPABASE_KEY from .env

Configure in Claude Code settings.json:
{
  "mcpServers": {
    "supabase": {
      "command": "python3.13",
      "args": ["/abs/path/to/scripts/supabase_mcp.py"],
      "env": {"PYTHONPATH": "venv_local/lib/python3.13/site-packages"}
    }
  }
}

Tools exposed:
  supabase_check   — test connection, returns status
  supabase_query   — SELECT rows from a table
  supabase_insert  — INSERT row into a table
  supabase_sql     — run raw SQL via Supabase RPC (requires rpc function)
"""
import json
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

TOOLS = [
    {
        "name": "supabase_check",
        "description": "Test the Supabase REST API connection. Returns HTTP status and list of accessible tables.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "supabase_query",
        "description": "SELECT rows from a Supabase table.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "table":   {"type": "string", "description": "Table name"},
                "filters": {"type": "object", "description": "PostgREST filters e.g. {\"status\": \"eq.success\"}"},
                "select":  {"type": "string", "description": "Columns to return (default: *)"},
                "limit":   {"type": "integer", "description": "Max rows (default: 20)"},
                "order":   {"type": "string", "description": "Order e.g. 'ts.desc'"},
            },
            "required": ["table"],
        },
    },
    {
        "name": "supabase_insert",
        "description": "INSERT a row into a Supabase table.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "table": {"type": "string", "description": "Table name"},
                "row":   {"type": "object", "description": "Key-value pairs to insert"},
            },
            "required": ["table", "row"],
        },
    },
]


def _call_tool(name: str, args: dict) -> str:
    if name == "supabase_check":
        r = requests.get(f"{SUPABASE_URL}/rest/v1/", headers=HEADERS, timeout=10)
        tables = list(r.json().keys()) if r.status_code == 200 else []
        return json.dumps({"status": r.status_code, "tables": tables})

    if name == "supabase_query":
        table  = args["table"]
        params = {
            "select": args.get("select", "*"),
            "limit":  str(args.get("limit", 20)),
        }
        for k, v in (args.get("filters") or {}).items():
            params[k] = v
        if args.get("order"):
            params["order"] = args["order"]
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}", params=params, headers=HEADERS, timeout=15
        )
        r.raise_for_status()
        rows = r.json()
        return json.dumps({"count": len(rows), "rows": rows})

    if name == "supabase_insert":
        table = args["table"]
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            json=args["row"],
            headers={**HEADERS, "Prefer": "return=representation"},
            timeout=15,
        )
        r.raise_for_status()
        return json.dumps({"inserted": r.json()})

    return json.dumps({"error": f"Unknown tool: {name}"})


# ── MCP stdio protocol (Content-Length framing) ───────────────────────────────
def _read():
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line or line in (b'\r\n', b'\n'):
            break
        if b':' in line:
            k, v = line.decode('utf-8', errors='replace').split(':', 1)
            headers[k.strip().lower()] = v.strip()
    length = int(headers.get('content-length', 0))
    if length:
        return json.loads(sys.stdin.buffer.read(length))
    return None


def _write(msg: dict):
    body = json.dumps(msg).encode('utf-8')
    sys.stdout.buffer.write(f'Content-Length: {len(body)}\r\n\r\n'.encode())
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()


def _handle(req: dict) -> dict | None:
    method = req.get("method", "")
    req_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "supabase-mcp", "version": "1.0.0"},
            },
        }

    if method == "notifications/initialized":
        return None  # notification — no response

    if method == "tools/list":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {"tools": TOOLS},
        }

    if method == "tools/call":
        name = req["params"]["name"]
        args = req["params"].get("arguments", {})
        try:
            content = _call_tool(name, args)
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": content}]},
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Error: {e}"}],
                    "isError": True,
                },
            }

    if req_id is not None:
        return {
            "jsonrpc": "2.0", "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }
    return None


def main():
    while True:
        try:
            req = _read()
            if req is None:
                break
            resp = _handle(req)
            if resp is not None:
                _write(resp)
        except (EOFError, BrokenPipeError):
            break
        except Exception as e:
            sys.stderr.write(f"[supabase_mcp] error: {e}\n")


if __name__ == "__main__":
    main()
