# AI Secretary

A local, terminal-based AI assistant accessible via the `sec` command. It uses Claude's tool-use API to interact with your Google Calendar and Gmail — all from your terminal, with credentials and history stored entirely on your machine.

---

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Google OAuth Setup](#google-oauth-setup)
- [Usage](#usage)
- [Commands](#commands)
- [Available Tools](#available-tools)
- [Database](#database)
- [Project Structure](#project-structure)
- [Security](#security)

---

## Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) — fast Python package manager
- A Zsh or Bash terminal (Linux / WSL2)
- An [Anthropic API key](https://console.anthropic.com/)
- A Google Cloud project with Calendar and Gmail APIs enabled

---

## Installation

**1. Clone the repository and enter the project directory:**

```bash
git clone <your-repo-url> AI_Secretary
cd AI_Secretary
```

**2. Install dependencies and the `sec` command:**

```bash
uv sync
```

This creates a `.venv` inside the project and installs all packages listed in `pyproject.toml`, including the `sec` entry point.

**3. Add the global alias to your shell:**

Append the following to `~/.zshrc` (or `~/.bashrc`):

```zsh
export SECRETARY_VENV="$HOME/VsCode_Projects/AI_Secretary/.venv"
alias sec="$SECRETARY_VENV/bin/sec"
```

Then reload your shell:

```bash
source ~/.zshrc
```

You can now run `sec` from any directory.

---

## Configuration

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

Open `.env` and set:

```env
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-opus-4-7
GOOGLE_CLIENT_SECRET_PATH=credentials/google_client_secret.json
```

| Variable                    | Description                                 | Default                                 |
| --------------------------- | ------------------------------------------- | --------------------------------------- |
| `ANTHROPIC_API_KEY`         | Your Anthropic API key                      | _(required)_                            |
| `ANTHROPIC_MODEL`           | Claude model to use                         | `claude-opus-4-7`                       |
| `GOOGLE_CLIENT_SECRET_PATH` | Path to your downloaded OAuth client secret | `credentials/google_client_secret.json` |

> `.env` is listed in `.gitignore` and will never be committed.

---

## Google OAuth Setup

The secretary needs permission to read/write your Google Calendar and Gmail. This is done once via OAuth2.

**Step 1 — Create a Google Cloud project:**

1. Go to [console.cloud.google.com](https://console.cloud.google.com/)
2. Create a new project (or use an existing one)

**Step 2 — Enable the required APIs:**

In the project, go to **APIs & Services → Library** and enable:

- Google Calendar API
- Gmail API

**Step 3 — Create OAuth credentials:**

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth 2.0 Client ID**
3. Choose **Desktop app** as the application type
4. Download the JSON file

**Step 4 — Place the file:**

```bash
mkdir -p credentials
mv ~/Downloads/client_secret_*.json credentials/google_client_secret.json
```

**Step 5 — Authenticate:**

```bash
sec auth
```

A browser window opens. Sign in with your Google account and grant the requested permissions. The access token is stored securely in your OS keyring (GNOME Keyring on Linux / Credential Manager on Windows) — never written to disk as a plain file.

On subsequent runs, the token is refreshed automatically. You only need to run `sec auth` again if you revoke access or switch accounts.

---

## Usage

Start an interactive session:

```bash
sec
```

The secretary greets you, then waits for your input. Type your request in plain English:

```
╭────────────────────────────────────────────────────────────────╮
│                        AI Secretary                            │
│               Ctrl+C to exit · sec auth to connect Google     │
╰────────────────────────────────────────────────────────────────╯

Secretary ready. Type your request, or Ctrl+C to exit.

You: What's on my calendar today?
  ⚙  list_calendar_events(date='2026-05-25')

Secretary:
Events on 2026-05-25:
  09:00  Standup
  14:00  1:1 with manager
  16:30  Team retrospective
```

Type `exit`, `quit`, or press `Ctrl+C` to end the session.

---

## Commands

| Command             | Description                                                          |
| ------------------- | -------------------------------------------------------------------- |
| `sec`               | Start an interactive AI session                                      |
| `sec auth`          | Authenticate with Google (run once, or to re-authenticate)           |
| `sec history`       | Show recent session history                                          |
| `sec history -n 25` | Show the last 25 sessions                                            |
| `sec context`       | Show persisted user context (facts the AI remembers across sessions) |
| `sec --help`        | Show all available commands                                          |

---

## Available Tools

These are the Python functions registered as AI-callable tools. The model decides which ones to call based on your request — you never have to invoke them directly.

### Calendar

| Tool                            | What it does                                                                   |
| ------------------------------- | ------------------------------------------------------------------------------ |
| `list_calendar_events`          | Lists events for a given date                                                  |
| `list_calendar_events_with_ids` | Same as above, but includes event IDs (required for deletion)                  |
| `create_calendar_event`         | Creates a new event with title, date, start/end time, and optional description |
| `delete_calendar_event`         | Deletes an event by its ID                                                     |

### Gmail

| Tool          | What it does                                                                |
| ------------- | --------------------------------------------------------------------------- |
| `list_emails` | Lists recent inbox emails; supports Gmail search queries (e.g. `is:unread`) |
| `read_email`  | Reads the full body of an email by its ID                                   |
| `send_email`  | Sends a plain-text email to a recipient                                     |

**Example requests:**

```
You: Schedule a team lunch for tomorrow at noon to 1pm
You: Do I have any unread emails from my manager?
You: Read the last email from Alice
You: Send a reply to bob@example.com saying I'll be 5 minutes late
You: Delete the 3pm meeting on Friday
```

---

## Database

Session history and user context are stored in a local SQLite database at:

```
~/.local/share/secretary/history.db
```

The file is created automatically on first run and restricted to owner-only permissions (`chmod 600`).

### Schema

**`sessions`** — one row per conversation:

| Column       | Type    | Description                                    |
| ------------ | ------- | ---------------------------------------------- |
| `id`         | INTEGER | Auto-incrementing primary key                  |
| `created_at` | TEXT    | ISO timestamp of when the session started      |
| `summary`    | TEXT    | Optional AI-generated summary (future feature) |

**`messages`** — every turn in every session:

| Column       | Type    | Description                    |
| ------------ | ------- | ------------------------------ |
| `id`         | INTEGER | Auto-incrementing primary key  |
| `session_id` | INTEGER | Foreign key → `sessions.id`    |
| `role`       | TEXT    | `user`, `assistant`, or `tool` |
| `content`    | TEXT    | Full message text              |
| `created_at` | TEXT    | ISO timestamp                  |

**`user_context`** — persistent key-value facts:

| Column       | Type | Description                                 |
| ------------ | ---- | ------------------------------------------- |
| `key`        | TEXT | Unique fact name, e.g. `preferred_timezone` |
| `value`      | TEXT | The stored value                            |
| `updated_at` | TEXT | Last updated timestamp                      |

### Inspecting the database directly

```bash
sqlite3 ~/.local/share/secretary/history.db

-- List all sessions
SELECT id, created_at, summary FROM sessions ORDER BY created_at DESC LIMIT 10;

-- Read messages from a specific session
SELECT role, content FROM messages WHERE session_id = 1 ORDER BY created_at;

-- View stored user context
SELECT * FROM user_context;
```

---

## Project Structure

```
AI_Secretary/
├── pyproject.toml              # Package config, dependencies, sec entry point
├── .env.example                # Template for environment variables
├── .env                        # Your actual secrets (gitignored)
├── .gitignore
├── credentials/
│   └── google_client_secret.json   # OAuth client config (gitignored)
└── src/
    └── secretary/
        ├── main.py             # Typer CLI: sec, sec auth, sec history, sec context
        ├── config.py           # Settings loaded from .env via pydantic-settings
        ├── agent/
        │   ├── registry.py     # @tool decorator — registers Python functions as AI tools
        │   └── loop.py         # Multi-turn agentic execution loop
        ├── auth/
        │   └── google.py       # OAuth2 flow; token storage via OS keyring
        ├── integrations/
        │   ├── calendar.py     # Google Calendar tool implementations
        │   └── gmail.py        # Gmail tool implementations
        ├── storage/
        │   ├── db.py           # SQLite connection, DDL, query helpers
        │   └── models.py       # Dataclasses: Session, Message, UserContext
        └── ui/
            └── console.py      # Rich console helpers: banner, spinner, errors
```

---

## Security

| Concern              | How it's handled                                                                            |
| -------------------- | ------------------------------------------------------------------------------------------- |
| API keys             | Read from `.env` at startup; `.env` is gitignored                                           |
| Google OAuth tokens  | Stored in the OS keyring (GNOME Keyring / Credential Manager), never in a file              |
| `client_secret.json` | Kept in `credentials/` which is gitignored                                                  |
| Database file        | Restricted to owner-only permissions (`600`) on creation                                    |
| OAuth redirect       | Uses `port=0` — a random ephemeral port per flow, not a fixed predictable one               |
| Tool results         | Passed to the model as structured `tool_result` blocks, not injected into the system prompt |

---

## Adding New Tools

To expose a new Python function to the AI, decorate it with `@tool` and import the module in `main.py`:

```python
# src/secretary/integrations/my_tool.py
from secretary.agent.registry import tool

@tool
def get_weather(city: str) -> str:
    """Get the current weather for a city.

    Args:
        city: The city name, e.g. 'Buenos Aires'.
    """
    # ... your implementation
    return f"Sunny, 22°C in {city}."
```

Then register the import in [src/secretary/main.py](src/secretary/main.py) alongside the existing integrations:

```python
import secretary.integrations.my_tool  # noqa: F401
```

The `@tool` decorator auto-generates the JSON schema Anthropic needs from your type annotations and docstring — no extra configuration required.
