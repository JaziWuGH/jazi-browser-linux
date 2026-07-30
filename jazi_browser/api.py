"""
FastAPI server — the HTTP API that AI agents talk to.

Endpoints — Space management and tool execution:
- Space management (create, list, close)
- Tool execution (run JS tools on a page in a space)
- Snapshot retrieval
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .manager import get_manager, shutdown as shutdown_manager, DEFAULT_PROFILE_DIR
from .space import SpaceManager
from .tools import (
    navigate, click, fill,
    snapshot as take_snapshot_tool,
    wait_for, capture, get_text, eval_js,
)
from .snapshot import snapshot as take_page_snapshot

logger = logging.getLogger(__name__)

# Global space manager
space_mgr = SpaceManager()

# ---- Lifespan ----

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start browser on server startup, shut down on exit."""
    try:
        mgr = await get_manager()
        # Create default space
        await space_mgr.create("default", mgr, inherit_cookies=True)
        logger.info("Jazi Browser server ready")
    except Exception as e:
        logger.error(f"Failed to start browser: {e}")
    yield
    await space_mgr.close_all()
    await shutdown_manager()


app = FastAPI(
    title="Jazi Browser (Linux)",
    description="A browser purpose-built for AI agents on Linux",
    version="0.1.0",
    lifespan=lifespan,
)


# ---- Request/Response Models ----

class NavigateRequest(BaseModel):
    url: str
    timeout: int = 30000


class ClickRequest(BaseModel):
    ref: str


class FillRequest(BaseModel):
    ref: str
    value: str


class WaitRequest(BaseModel):
    text: str
    timeout: int = 15000


class CreateSpaceRequest(BaseModel):
    name: str
    inherit_cookies: bool = True


# ---- Space Endpoints ----

@app.post("/space")
async def create_space(req: CreateSpaceRequest):
    """Create a new isolated Space for an agent."""
    try:
        mgr = await get_manager()
        space = await space_mgr.create(req.name, mgr, inherit_cookies=req.inherit_cookies)
        return {
            "name": space.name,
            "page_count": len(space.context.pages),
            "spaces": space_mgr.list_spaces(),
        }
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/spaces")
async def list_spaces():
    """List all active spaces."""
    return {"spaces": space_mgr.list_spaces()}


@app.delete("/space/{name}")
async def close_space(name: str):
    """Close and remove a space."""
    if name == "default":
        raise HTTPException(status_code=400, detail="Cannot close default space")
    if name not in space_mgr._spaces:
        raise HTTPException(status_code=404, detail=f"Space '{name}' not found")
    await space_mgr.close(name)
    return {"closed": name, "spaces": space_mgr.list_spaces()}


# ---- Page Action Endpoints ----

@app.post("/space/{space_name}/navigate")
async def space_navigate(space_name: str, req: NavigateRequest):
    """Navigate to a URL in a space."""
    space = space_mgr.get(space_name)
    if not space:
        raise HTTPException(status_code=404, detail=f"Space '{space_name}' not found")

    page = await space.active_page
    result = await navigate(page, req.url, req.timeout)
    return result


@app.post("/space/{space_name}/click")
async def space_click(space_name: str, req: ClickRequest):
    """Click an element in a space."""
    space = space_mgr.get(space_name)
    if not space:
        raise HTTPException(status_code=404, detail=f"Space '{space_name}' not found")

    page = await space.active_page
    result = await click(page, req.ref)
    return result


@app.post("/space/{space_name}/fill")
async def space_fill(space_name: str, req: FillRequest):
    """Fill an input in a space."""
    space = space_mgr.get(space_name)
    if not space:
        raise HTTPException(status_code=404, detail=f"Space '{space_name}' not found")

    page = await space.active_page
    result = await fill(page, req.ref, req.value)
    return result


@app.get("/space/{space_name}/snapshot")
async def space_snapshot(space_name: str, compact: bool = True):
    """Get page snapshot from a space."""
    space = space_mgr.get(space_name)
    if not space:
        raise HTTPException(status_code=404, detail=f"Space '{space_name}' not found")

    page = await space.active_page
    result = await take_page_snapshot(page, compact=compact)
    return {"snapshot": result, "url": page.url}


@app.post("/space/{space_name}/wait")
async def space_wait(space_name: str, req: WaitRequest):
    """Wait for text in a space."""
    space = space_mgr.get(space_name)
    if not space:
        raise HTTPException(status_code=404, detail=f"Space '{space_name}' not found")

    page = await space.active_page
    result = await wait_for(page, req.text, req.timeout)
    return result


@app.post("/space/{space_name}/capture")
async def space_capture(space_name: str):
    """Take a screenshot in a space."""
    space = space_mgr.get(space_name)
    if not space:
        raise HTTPException(status_code=404, detail=f"Space '{space_name}' not found")

    page = await space.active_page
    result = await capture(page)
    return result


@app.get("/space/{space_name}/text")
async def space_text(space_name: str, max_chars: int = 5000):
    """Get visible text from a space."""
    space = space_mgr.get(space_name)
    if not space:
        raise HTTPException(status_code=404, detail=f"Space '{space_name}' not found")

    page = await space.active_page
    result = await get_text(page, max_chars)
    return result


@app.post("/space/{space_name}/eval")
async def space_eval(space_name: str, js_code: str = Query(...)):
    """Evaluate JavaScript in a space."""
    space = space_mgr.get(space_name)
    if not space:
        raise HTTPException(status_code=404, detail=f"Space '{space_name}' not found")

    page = await space.active_page
    result = await eval_js(page, js_code)
    return result


# ---- Health & Status ----

@app.get("/health")
async def health():
    """Health check endpoint."""
    mgr = None
    try:
        mgr = await get_manager()
        browser_ready = mgr.is_ready
    except Exception:
        browser_ready = False

    return {
        "status": "ok" if browser_ready else "degraded",
        "browser_ready": browser_ready,
        "spaces": len(space_mgr._spaces),
        "profile_dir": str(DEFAULT_PROFILE_DIR),
    }
