"""Fault injection state machine for the SSH diagnostics demo.

The whole point of this app is that an SRE can SSH in with the new Python
helper aliases and walk a fault back to its root cause. To keep that demo
honest, the faults need to mutate **real** runtime state — env vars the
``ai-*`` aliases will inspect, ports the ``checkport`` alias will probe,
imports the ``showpkgs`` alias will reveal — not just toggle a boolean.

A subtlety: env mutations in this Python process only affect the worker, not
new SSH shells. So every transition also writes ``FAULT_ENV_FILE`` — an
``export``-style file that the operator sources from their SSH session to
make the alias diagnostics see the same broken state the app sees.

Each fault mode applies on transition (when ``set_mode`` is called) and is
read by ``foundry_client`` and the routes in ``main.py``. The healthy
baseline is captured on import so ``off`` always restores known-good state.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Optional

_LOG = logging.getLogger(__name__)


class FaultMode(str, Enum):
    OFF = "off"
    BAD_CREDS = "bad-creds"
    WRONG_ENDPOINT = "wrong-endpoint"
    DNS_FAIL = "dns-fail"
    PORT_MISMATCH = "port-mismatch"
    DEP_IMPORT_ERROR = "dep-import-error"
    LATENCY_SPIKE = "latency-spike"


# Env vars the foundry client + aliases read. We snapshot them at startup so
# we can always restore the healthy baseline when the operator runs `off`.
# AZURE_AI_FOUNDRY_ENDPOINT + AZURE_AI_MODEL are the canonical names that
# the ai-* SSH aliases read; the app reads the same vars so that breaking
# one breaks both — which is the point of the demo.
_ENV_KEYS = (
    "AZURE_AI_FOUNDRY_ENDPOINT",
    "AZURE_AI_MODEL",
    "AZURE_CLIENT_ID",
)

# Bogus values used to engineer each failure. We deliberately use real-looking
# strings so the ai-* aliases produce informative output (a DNS lookup, a
# 401, an "endpoint not found", etc.) rather than a generic config error.
_WRONG_ENDPOINT = "https://this-resource-does-not-exist.openai.azure.com/"
_DNS_FAIL_HOST = "https://no-such-host.invalid.example/"
# A non-existent managed identity client id. AOAI will return 401 because
# the token request itself fails.
_BAD_CLIENT_ID = "00000000-0000-0000-0000-000000000000"


@dataclass
class FaultState:
    mode: FaultMode = FaultMode.OFF
    latency_ms: int = 0
    notes: str = ""
    baseline_env: Dict[str, Optional[str]] = field(default_factory=dict)
    dep_import_failed: bool = False


_LOCK = threading.Lock()
_STATE = FaultState()

# /home/site is the persistent mount on App Service Linux. Any path under
# /home survives slot swaps and restarts and is visible to SSH sessions.
FAULT_ENV_FILE = Path(
    os.environ.get("FAULT_ENV_FILE", "/home/site/diagnostics/fault.env")
)


def init_baseline() -> None:
    """Snapshot the healthy env at process start. Call once from main."""
    with _LOCK:
        _STATE.baseline_env = {k: os.environ.get(k) for k in _ENV_KEYS}
    _write_env_file()


def _restore_baseline() -> None:
    for k, v in _STATE.baseline_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    _STATE.latency_ms = 0
    _STATE.dep_import_failed = False
    _STATE.notes = ""


def _write_env_file() -> None:
    """Mirror current env into a sourceable file for SSH sessions.

    SSH shells inherit env from the container at session start, so they
    can't see Python's ``os.environ`` mutations. The operator runs
    ``source /home/site/diagnostics/fault.env`` to apply the active fault
    to their shell, then the ai-* aliases produce realistic output.
    """
    try:
        FAULT_ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"# Active fault: {_STATE.mode.value}", f"# {_STATE.notes}", ""]
        for k in _ENV_KEYS:
            v = os.environ.get(k)
            if v is None:
                lines.append(f"unset {k}")
            else:
                # Single-quote escape: ' -> '\''
                safe = v.replace("'", "'\\''")
                lines.append(f"export {k}='{safe}'")
        FAULT_ENV_FILE.write_text("\n".join(lines) + "\n")
    except Exception:  # noqa: BLE001 — env file is a convenience, not load-bearing
        _LOG.exception("Failed to write fault env file %s", FAULT_ENV_FILE)


def _snapshot_unlocked() -> dict:
    return {
        "mode": _STATE.mode.value,
        "latency_ms": _STATE.latency_ms,
        "notes": _STATE.notes,
        "env": {k: os.environ.get(k) for k in _ENV_KEYS},
        "listening_port": os.environ.get("PORT") or os.environ.get("WEBSITES_PORT") or "8000",
        "fault_env_file": str(FAULT_ENV_FILE),
    }


def get_state() -> dict:
    with _LOCK:
        return _snapshot_unlocked()


def set_mode(mode: FaultMode) -> dict:
    """Apply ``mode`` to live process state and return the new state."""
    with _LOCK:
        _restore_baseline()
        _STATE.mode = mode

        if mode is FaultMode.OFF:
            _STATE.notes = "Baseline restored. ai-test should report Connected."

        elif mode is FaultMode.BAD_CREDS:
            os.environ["AZURE_CLIENT_ID"] = _BAD_CLIENT_ID
            _STATE.notes = (
                "AZURE_CLIENT_ID swapped to a non-existent identity. "
                "ai-access-check / ai-diagnose / ai-test will fail at auth."
            )

        elif mode is FaultMode.WRONG_ENDPOINT:
            os.environ["AZURE_AI_FOUNDRY_ENDPOINT"] = _WRONG_ENDPOINT
            _STATE.notes = (
                "AZURE_AI_FOUNDRY_ENDPOINT points at a resource that does not exist. "
                "ai-dns will resolve openai.azure.com but ai-curl will 404."
            )

        elif mode is FaultMode.DNS_FAIL:
            os.environ["AZURE_AI_FOUNDRY_ENDPOINT"] = _DNS_FAIL_HOST
            _STATE.notes = (
                "AZURE_AI_FOUNDRY_ENDPOINT points at an unresolvable host. "
                "ai-dns will surface NXDOMAIN; install-nettools + nslookup confirms it."
            )

        elif mode is FaultMode.PORT_MISMATCH:
            os.environ["WEBSITES_PORT"] = "9999"
            _STATE.notes = (
                "WEBSITES_PORT changed to 9999 but uvicorn still binds 8000. "
                "checkport + appcurl + appconfig show the mismatch."
            )

        elif mode is FaultMode.DEP_IMPORT_ERROR:
            _STATE.dep_import_failed = True
            _STATE.notes = (
                "Simulated ImportError on /chat. applogs / deploylogs / showpkgs "
                "reveal which package the app expected."
            )

        elif mode is FaultMode.LATENCY_SPIKE:
            _STATE.latency_ms = 4000
            _STATE.notes = (
                "4s of synthetic latency added to every /chat. "
                "ai-latency + ai-curl show the inflated round-trip."
            )

        _LOG.warning("Fault mode set to %s | %s", mode.value, _STATE.notes)
        snapshot = _snapshot_unlocked()
    _write_env_file()
    return snapshot


def current_mode() -> FaultMode:
    with _LOCK:
        return _STATE.mode


async def apply_pre_call_delay() -> None:
    """Honour the active latency-spike fault before talking to Foundry."""
    delay = 0
    with _LOCK:
        if _STATE.mode is FaultMode.LATENCY_SPIKE:
            delay = _STATE.latency_ms
    if delay:
        await asyncio.sleep(delay / 1000.0)


def maybe_raise_import_error() -> None:
    """Simulate a missing dependency on /chat without breaking the process."""
    with _LOCK:
        if _STATE.mode is FaultMode.DEP_IMPORT_ERROR or _STATE.dep_import_failed:
            raise ImportError(
                "No module named 'tiktoken'  # simulated by faults.py — "
                "use `showpkgs | grep tiktoken` and `applogs` to confirm."
            )
