"""FastAPI entrypoint for the App Service SSH Diagnostics demo.

Endpoints:
  GET  /              — landing page that doubles as an SSH alias cheat sheet
  GET  /health        — liveness + current fault mode
  POST /chat          — call Azure AI Foundry; success/failure shape depends on the active fault
  POST /admin/fault   — toggle one of the seven fault modes
  GET  /admin/state   — what env the process actually sees right now

The whole point of this app is to be diagnosed over SSH, so the surface is
intentionally small: one upstream call, one fault switch, and a state view.
"""

from __future__ import annotations

import logging
import os
import socket

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app import faults, foundry_client
from app.pages import INDEX_HTML

_LOG = logging.getLogger("ssh-diagnostics")
logging.basicConfig(level=logging.INFO)


def _configure_azure_monitor_if_available() -> bool:
    if not os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        return False
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor()
        return True
    except Exception:  # noqa: BLE001 — never let telemetry kill startup
        _LOG.exception("Failed to wire Azure Monitor; continuing without it")
        return False


_AI_WIRED = _configure_azure_monitor_if_available()
faults.init_baseline()


app = FastAPI(
    title="App Service SSH Diagnostics — Python",
    description=(
        "A deliberately fragile Foundry-backed FastAPI app, paired with the new "
        "Python SSH helper aliases on Azure App Service for Linux. SSH in, run "
        "`apphelp`, and walk each fault back to its root cause."
    ),
    version="0.1.0",
)


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)


class FaultRequest(BaseModel):
    mode: faults.FaultMode


def _instance_id() -> str:
    return os.environ.get("WEBSITE_INSTANCE_ID") or socket.gethostname()


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> HTMLResponse:
    return HTMLResponse(content=INDEX_HTML)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "app_insights": _AI_WIRED,
        "instance_id": _instance_id(),
        "fault_mode": faults.current_mode().value,
    }


@app.post("/chat")
async def chat(req: ChatRequest) -> dict:
    try:
        return await foundry_client.ask(req.prompt)
    except ImportError as exc:
        _LOG.exception("Simulated import error in /chat")
        raise HTTPException(status_code=500, detail=f"ImportError: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — surface the message for the SSH demo
        _LOG.exception("Foundry call failed")
        raise HTTPException(status_code=502, detail=f"{type(exc).__name__}: {exc}") from exc


@app.post("/admin/fault")
def set_fault(req: FaultRequest) -> dict:
    return faults.set_mode(req.mode)


@app.get("/admin/state")
def admin_state() -> dict:
    state = faults.get_state()
    state["instance_id"] = _instance_id()
    state["app_insights"] = _AI_WIRED
    return state
