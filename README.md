# MCP (Model Context Protocol) – Step-by-Step Guide

A practical, beginner-friendly guide to working with **MCP** on Windows using **Python, uv and FastMCP**, and Claude Desktop.

You will learn how to:

1. [Add an MCP server using the Connect option](#1-add-an-mcp-server-using-the-connect-option)
2. [Add an MCP server using the JSON config file](#2-add-an-mcp-server-using-the-json-config-file)
3. [Create a local MCP server, test it with MCP Inspector and connect it to Claude Desktop](#3-create-a-local-mcp-server)
4. [Build and connect a remote MCP server (and why we need a proxy)](#4-build-and-connect-a-remote-mcp-server)
5. [Build an MCP client](#5-build-an-mcp-client)
6. [Common problems and solutions](#6-common-problems-and-solutions)

---

## Prerequisites

| Tool | Why | Check |
|------|-----|-------|
| Python 3.10+ | Run the server | `python --version` |
| [uv](https://docs.astral.sh/uv/) | Package and project manager | `uv --version` |
| [Node.js LTS](https://nodejs.org) | Needed by MCP Inspector (`npx`) and the `mcp-remote` proxy | `node --version` |
| Claude Desktop | The MCP host/client | Open the app once after installing |

Install uv (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

---

## 1. Add an MCP server using the Connect option

Use this for servers that already exist (official or third-party connectors, or any remote server that has a URL). No code needed.

**Steps**

1. Open **Claude Desktop** and go to **Settings → Connectors** (on some versions: **Settings → Extensions**).
2. Click **Browse connectors** (or **Browse extensions**) and pick a service, for example Filesystem, Indeed, or Google Drive.
3. Click **Connect** / **Install** and follow the sign-in or permission prompts.
4. For a remote server that is not in the directory, click **Add custom connector**, give it a name, paste the server URL (for example `https://your-server.example.com/mcp`) and click **Add**.
5. Start a **new chat**, click the **+** or tools icon in the message box and make sure the connector is toggled on.
6. Test it with a prompt that needs the tool, for example *"List the files on my Desktop"*.

> Menu names change between Claude Desktop versions. If you can't find an option, search the Settings page for "Connectors" or "Extensions". Custom connectors may only be available on some plans.

---

## 2. Add an MCP server using the JSON config file

Use this for servers you run on your own machine (local/stdio servers).

### Step 1 – Open the config file

In Claude Desktop go to **Settings → Developer → Edit Config**. This always opens the correct `claude_desktop_config.json`, even if you installed the Microsoft Store version.

Typical locations:

- Normal install: `%APPDATA%\Claude\claude_desktop_config.json`
- Microsoft Store install: `%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\claude_desktop_config.json`

### Step 2 – Add your server inside `mcpServers`

```json
{
  "mcpServers": {
    "expense-tracker": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "C:\\Users\\YOUR_NAME\\path\\to\\Expense_Tracker",
        "fastmcp",
        "run",
        "main.py"
      ]
    }
  }
}
```

Rules to remember:

- The file must contain **one single JSON object**. Do not paste a second `{ ... }` block under the first one.
- If `mcpServers` already exists, add your server **inside it** and separate entries with a comma.
- On Windows use double backslashes (`\\`) in paths, or forward slashes (`/`).

Example with two servers:

```json
{
  "mcpServers": {
    "manim-server": {
      "command": "C:/Python313/python.exe",
      "args": ["C:/Users/YOUR_NAME/manim-mcp-server/src/manim_server.py"]
    },
    "expense-tracker": {
      "command": "uv",
      "args": ["run", "--directory", "C:\\Users\\YOUR_NAME\\Expense_Tracker", "fastmcp", "run", "main.py"]
    }
  },
  "preferences": { }
}
```

### Step 3 – Validate the JSON (optional but useful)

```powershell
$p = "$env:APPDATA\Claude\claude_desktop_config.json"   # use your real path
(Get-Content $p -Raw | ConvertFrom-Json).mcpServers | Get-Member -MemberType NoteProperty | Select Name
```

You should see every server name listed. A parse error means a comma or brace is wrong.

### Step 4 – Fully restart Claude Desktop

Closing the window is not enough. Quit it from the system tray, or run:

```powershell
Get-Process *claude* | Stop-Process -Force
```

Then reopen Claude Desktop and check **Settings → Developer**. Your server should be listed as **running**.

### Shortcut: `fastmcp install`

```powershell
uv run fastmcp install claude-desktop main.py
```

This writes the same entry into the config for you. It can fail with "Claude Desktop config directory not found" (see [problems](#6-common-problems-and-solutions)), in which case edit the file manually.

---

## 3. Create a local MCP server

### Step 1 – Create the project

```powershell
mkdir Expense_Tracker
cd Expense_Tracker
uv init
uv add fastmcp
uv run fastmcp version
```

> **Do not name your project `mcp`.** It shadows the real `mcp` package and breaks FastMCP with `No module named 'mcp.server'`. Use a name like `expense-tracker`.

### Step 2 – Write the server (`main.py`)

```python
import sqlite3
from pathlib import Path
from fastmcp import FastMCP

DB_PATH = Path(__file__).parent / "expenses.db"
mcp = FastMCP("Expense Tracker")


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                note TEXT DEFAULT ''
            )"""
        )


init_db()


@mcp.tool()
def add_expense(date: str, amount: float, category: str, note: str = "") -> dict:
    """Add an expense. Date format: YYYY-MM-DD."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO expenses (date, amount, category, note) VALUES (?, ?, ?, ?)",
            (date, amount, category, note),
        )
        return {"status": "ok", "id": cur.lastrowid}


@mcp.tool()
def list_expenses(start_date: str, end_date: str) -> list[dict]:
    """List expenses between two dates (inclusive)."""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, date, amount, category, note FROM expenses "
            "WHERE date BETWEEN ? AND ? ORDER BY date",
            (start_date, end_date),
        ).fetchall()
    cols = ["id", "date", "amount", "category", "note"]
    return [dict(zip(cols, r)) for r in rows]


@mcp.tool()
def summarize(start_date: str, end_date: str) -> list[dict]:
    """Total spending per category between two dates."""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT category, SUM(amount) FROM expenses "
            "WHERE date BETWEEN ? AND ? GROUP BY category",
            (start_date, end_date),
        ).fetchall()
    return [{"category": c, "total": t} for c, t in rows]


if __name__ == "__main__":
    mcp.run()
```

> Keep `mcp.run()` inside `if __name__ == "__main__":`. If it runs at module level, the inspector crashes with `RuntimeError: Already running asyncio in this thread`.

### Step 3 – Test with MCP Inspector

```powershell
uv run fastmcp dev inspector main.py
```

(Older FastMCP versions: `uv run fastmcp dev main.py`.)

1. A browser tab opens with the Inspector UI (Node.js is required).
2. Click **Connect**.
3. Open the **Tools** tab and click **List Tools**. You should see `add_expense`, `list_expenses` and `summarize`.
4. Select a tool, fill in the arguments and click **Run Tool** to check the output.

Fix any errors here before connecting to Claude Desktop.

### Step 4 – Connect to Claude Desktop

Follow [Section 2](#2-add-an-mcp-server-using-the-json-config-file) and add:

```json
"expense-tracker": {
  "command": "uv",
  "args": ["run", "--directory", "C:\\Users\\YOUR_NAME\\Expense_Tracker", "fastmcp", "run", "main.py"]
}
```

Restart Claude Desktop fully, open a new chat and try:

> *"Add an expense of 250 for food on 2026-10-13, then summarize this month."*

---

## 4. Build and connect a remote MCP server

A **local** server runs on your computer and talks to Claude Desktop over **stdio**. A **remote** server runs on a host or in the cloud and is reached over **HTTP**, so many people can use it without installing anything.

### Step 1 – Make the server run over HTTP

Change the last lines of `main.py`:

```python
if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
```

Run it:

```powershell
uv run python main.py
```

The MCP endpoint is now `http://localhost:8000/mcp`.

### Step 2 – Test the remote server

```powershell
uv run fastmcp dev inspector main.py
```

In the Inspector choose the **Streamable HTTP** transport, enter `http://localhost:8000/mcp` and click **Connect**.

### Step 3 – Deploy it (so it has a public URL)

Push the repo to GitHub and deploy it to a host such as **FastMCP Cloud**, Render, Railway or any VPS. After deployment you get a URL like `https://your-app.example.com/mcp`. Check the exact deployment steps in the video linked at the bottom of this README.

### Step 4 – Connect it to Claude Desktop

**Option A – Custom connector (no proxy):** Settings → Connectors → **Add custom connector** → paste the URL. Availability depends on your Claude plan and app version.

**Option B – JSON config with a proxy (works everywhere):**

#### Why we need a proxy

The `claude_desktop_config.json` file can only start **local stdio** programs. It cannot connect to an `https://` URL directly. If you put a remote URL in the config you get errors or the server never shows up. A **proxy** such as [`mcp-remote`](https://www.npmjs.com/package/mcp-remote) runs locally as a stdio server and forwards everything to your remote server, so Claude Desktop thinks it is talking to a local one.

```
Claude Desktop  <-- stdio -->  mcp-remote (proxy)  <-- HTTP -->  Remote MCP server
```

Config (requires Node.js):

```json
{
  "mcpServers": {
    "expense-tracker-remote": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://your-app.example.com/mcp"]
    }
  }
}
```

For a server on your own machine while testing:

```json
"args": ["-y", "mcp-remote", "http://localhost:8000/mcp", "--allow-http"]
```

Restart Claude Desktop fully and check **Settings → Developer**.

#### Problems we faced with remote servers and the fixes

| Problem | Cause | Fix |
|---------|-------|-----|
| Remote URL in the JSON config does nothing | Config only supports stdio commands | Use the `mcp-remote` proxy or a custom connector |
| `npx` is not recognized | Node.js missing or not on PATH | Install Node.js LTS and reopen the terminal |
| 404 or connection error | Wrong path | Use the exact endpoint, usually ending in `/mcp` (or `/sse` for SSE servers) |
| Proxy refuses `http://` URL | `mcp-remote` expects HTTPS | Add `--allow-http` for localhost only, use HTTPS in production |
| Works in Inspector, fails in Claude | Claude not fully restarted, or old cached auth | Kill all Claude processes and reopen |
| Server sleeps or times out on free hosting | Cold start | Open the URL once to wake it, then retry |

---

## 5. Build an MCP client

Claude Desktop is a client, but you can write your own with FastMCP.

### Step 1 – Create `client.py`

```python
import asyncio
from fastmcp import Client

# Local server: pass the path of the server file (stdio)
# Remote server: pass the URL, e.g. "https://your-app.example.com/mcp"
client = Client("main.py")


async def main():
    async with client:
        tools = await client.list_tools()
        print("Available tools:", [t.name for t in tools])

        result = await client.call_tool(
            "add_expense",
            {"date": "2026-10-13", "amount": 250, "category": "food", "note": "lunch"},
        )
        print("Result:", result.data)

        summary = await client.call_tool(
            "summarize", {"start_date": "2026-10-01", "end_date": "2026-10-31"}
        )
        print("Summary:", summary.data)


asyncio.run(main())
```

### Step 2 – Run it

```powershell
uv run python client.py
```

### Step 3 – Connect to a remote server

Change one line:

```python
client = Client("http://localhost:8000/mcp")
```

### Going further: client with an LLM

To let an LLM decide which tool to call, pass the tool list to your model (Gemini, GPT-4, Claude, etc.), execute the tool call it returns with `client.call_tool(...)`, and feed the result back to the model. Frameworks such as LangChain/LangGraph (`langchain-mcp-adapters`) can do this wiring for you.

---

## 6. Common problems and solutions

| # | Problem / error | Cause | Solution |
|---|-----------------|-------|----------|
| 1 | `fastmcp : The term 'fastmcp' is not recognized` | `uv add` installs into `.venv`, which is not on PATH | Use `uv run fastmcp ...` or activate `.venv\Scripts\Activate.ps1` |
| 2 | `ModuleNotFoundError: No module named 'mcp.server'` | Your project is named `mcp` and shadows the real package | Rename the project in `pyproject.toml`, delete any `mcp` folder or `mcp.py`, delete `.venv`, run `uv sync` |
| 3 | `Unknown command "main.py". Available commands: inspector, apps` | Newer FastMCP made `dev` a command group | `uv run fastmcp dev inspector main.py` |
| 4 | `RuntimeError: Already running asyncio in this thread` | `mcp.run()` is called at import time | Put it under `if __name__ == "__main__":` |
| 5 | Inspector does not open | Node.js missing | Install Node.js LTS |
| 6 | `Claude Desktop config directory not found` | Store version keeps config in another folder, or app never launched | Open Claude Desktop once, or edit the config via **Settings → Developer → Edit Config** |
| 7 | Server not shown in Developer tab | JSON invalid, entry outside `mcpServers`, or app not fully restarted | Validate the JSON (Section 2, Step 3), then kill all Claude processes and reopen |
| 8 | Two `{ ... }` blocks in the config file | Pasted a second object under the first | Keep one object, add the server inside the existing `mcpServers` with a comma |
| 9 | Server shows as **failed** | `uv` not found by Claude Desktop, wrong path, or server crashes | Use the full path from `(Get-Command uv).Source` as `command`, run the same command in PowerShell to see the error, read the logs |
| 10 | `PowerShell script execution is disabled` when activating venv | Execution policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| 11 | Backslash path errors in JSON | Single `\` is an escape character | Use `\\` or `/` |
| 12 | Pre-release FastMCP behaves oddly | `fastmcp==x.y.zrc1` installed | `uv add "fastmcp>=2.10"` |

### Where to find logs

```
%APPDATA%\Claude\logs\                                          (normal install)
%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\logs\   (Store install)
```

Look for `mcp.log` and `mcp-server-<name>.log`. If `mcp-server-<name>.log` doesn't exist, Claude never tried to start your server, which means the config entry is wrong or in the wrong file.

---

## Project structure

```
MCP/
├── Expense_Tracker/        # local MCP server (stdio)
│   ├── main.py
│   ├── pyproject.toml
│   └── expenses.db         # created automatically
├── remote_server/          # HTTP version of the server
├── client/                 # MCP client examples
│   └── client.py
└── README.md
```

Adjust this to match your repository.

---

## Video references

- Local MCP server: https://www.youtube.com/watch?v=tc2oOznpdE0&list=PLKnIA16_Rmva_oZ9F4ayUu9qcWgF7Fyc0&index=6
- Remote MCP server: https://www.youtube.com/watch?v=GF7-ZzUausU&list=PLKnIA16_Rmva_oZ9F4ayUu9qcWgF7Fyc0&index=7
- MCP client: https://www.youtube.com/watch?v=o4ajsc-tSBc&list=PLKnIA16_Rmva_oZ9F4ayUu9qcWgF7Fyc0&index=8

## Useful links

- FastMCP docs: https://gofastmcp.com
- MCP specification: https://modelcontextprotocol.io
- MCP Inspector: https://github.com/modelcontextprotocol/inspector
- mcp-remote: https://www.npmjs.com/package/mcp-remote

---

## Author

**Harsh Dethe** – Generative AI / ML Engineer
GitHub: [@harshdethe](https://github.com/harshdethe)
