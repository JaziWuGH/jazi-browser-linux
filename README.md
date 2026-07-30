# Jazi Browser (Linux)

**A browser purpose-built for AI agents on Linux.**

Inspired by [ego-lite](https://github.com/citrolabs/ego-lite), reimagined for Linux with Playwright + Python.

## Why?

AI agents need a browser that:
- **Preserves your logins** — inherits Chrome cookies, sessions, extensions
- **Works in parallel** — you browse normally while agents work in isolated Spaces
- **Speaks the agent's language** — JS-based direct page control, not CLI step-by-step
- **Produces clean snapshots** — LLM-friendly accessibility tree output

## Architecture

```
┌─────────────────────────────────────────────┐
│                  jazi                        │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │       FastAPI Server (:9222)         │   │
│  │   - Space management CRUD            │   │
│  │   - Tool execution endpoints         │   │
│  │   - Snapshot retrieval               │   │
│  └──────────┬───────────────────────────┘   │
│             │                                 │
│  ┌──────────▼───────────────────────────┐   │
│  │     BrowserManager (Playwright)       │   │
│  │   - Persistent Chromium profile       │   │
│  │   - Chrome data migration             │   │
│  │   - Permission auto-grant             │   │
│  └──────────┬───────────────────────────┘   │
│             │                                 │
│  ┌──────────▼───────────────────────────┐   │
│  │  Space 1     Space 2     Space 3     │   │
│  │  (Agent A)   (Agent B)   (You)       │   │
│  │  isolated    isolated    isolated     │   │
│  │  cookies     cookies     cookies      │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

## Quick Start

### Install

```bash
# Clone and install
git clone https://github.com/JaziWuGH/jazi-browser-linux
cd jazi-browser-linux
bash scripts/install.sh
```

### Start the server

```bash
# GUI mode (you can see the browser)
jazi serve

# Headless mode (for servers)
jazi serve --headless
```

### Create a Space for your agent

```bash
jazi space create myagent
jazi space list
```

### Navigate and control

```bash
# Navigate to a URL
curl -X POST http://127.0.0.1:9222/space/myagent/navigate \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'

# Get page snapshot
curl http://127.0.0.1:9222/space/myagent/snapshot

# Click an element by ref
curl -X POST http://127.0.0.1:9222/space/myagent/click \
  -H "Content-Type: application/json" \
  -d '{"ref": "@e3"}'

# Fill a form
curl -X POST http://127.0.0.1:9222/space/myagent/fill \
  -H "Content-Type: application/json" \
  -d '{"ref": "@e5", "value": "hello world"}'
```

### NodeJS-style tool execution

```bash
jazi --space myagent nodejs << 'EOF'
// Navigate first
await tools.navigate("https://github.com");
// Get snapshot
const snap = await tools.snapshot();
console.log(snap);
EOF
```

### Cookie Import/Export — cross-machine login migration

```bash
# Export all cookies from a Space
jazi cookies export --space default
# → ~/jazi-cookies-20260730-120000.json

# Preview a cookie file
jazi cookies inspect ~/jazi-cookies-20260730-120000.json

# Import into a Space (with --clear to wipe existing cookies first)
jazi cookies import ~/jazi-cookies-20260730-120000.json --space myagent --clear
```

**Cross-platform flow (Windows → Linux):**

1. On Windows Chrome: use [EditThisCookie](https://www.editthiscookie.com/) extension → Export to JSON
2. Copy JSON file to Linux
3. On Linux: `jazi cookies import cookies.json`
4. All login sessions preserved. No re-authentication needed.

## API Reference

### Space Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/space` | Create a new space |
| GET | `/spaces` | List all spaces |
| DELETE | `/space/{name}` | Close a space |

### Page Actions (per space)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/space/{name}/navigate` | Navigate to URL |
| GET | `/space/{name}/snapshot` | Get page snapshot |
| POST | `/space/{name}/click` | Click element by @eN ref |
| POST | `/space/{name}/fill` | Fill input by @eN ref |
| POST | `/space/{name}/wait` | Wait for text |
| POST | `/space/{name}/capture` | Take screenshot |
| GET | `/space/{name}/text` | Get visible text |
| POST | `/space/{name}/eval` | Evaluate JS |

Full API docs at `http://127.0.0.1:9222/docs` when server is running.

## Features

- ✅ **Chrome profile migration** — cookies, logins, preferences carried over
- ✅ **Isolated Spaces** — each agent gets its own BrowserContext
- ✅ **LLM-friendly snapshots** — accessibility tree with @eN ref IDs for interaction
- ✅ **Direct JS control** — navigate, click, fill, wait, capture, eval
- ✅ **HTTP API** — any AI agent can call it via REST
- ✅ **Parallel execution** — multiple Spaces run concurrently
- ✅ **Local data** — everything stays on your machine

## License

MIT
