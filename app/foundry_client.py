"""Thin Azure AI Foundry / Azure OpenAI client.

Uses managed identity end-to-end so the new ``ai-test`` / ``ai-access-check``
aliases have something interesting to report.

We deliberately read env vars on every call (not at import time) because the
fault injector mutates them in place — that is the whole point of the demo.
"""

from __future__ import annotations

import logging
import os
from typing import Tuple

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from . import faults

_LOG = logging.getLogger(__name__)

AOAI_ENDPOINT_ENV = "AZURE_AI_FOUNDRY_ENDPOINT"
AOAI_DEPLOYMENT_ENV = "AZURE_AI_MODEL"
AOAI_API_VERSION = "2024-10-21"


def _build_client() -> Tuple[AzureOpenAI, str, str]:
    endpoint = os.environ.get(AOAI_ENDPOINT_ENV)
    deployment = os.environ.get(AOAI_DEPLOYMENT_ENV, "gpt-4o-mini")
    if not endpoint:
        raise RuntimeError(
            f"{AOAI_ENDPOINT_ENV} is not set. SSH in and run `appconfig` / `appenv | grep AZURE_AI_FOUNDRY_ENDPOINT`."
        )
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )
    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_version=AOAI_API_VERSION,
        azure_ad_token_provider=token_provider,
    )
    return client, deployment, endpoint


async def ask(prompt: str) -> dict:
    """Send a single chat completion to Foundry and return a small summary."""
    faults.maybe_raise_import_error()
    await faults.apply_pre_call_delay()

    client, deployment, endpoint = _build_client()
    completion = client.chat.completions.create(
        model=deployment,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a terse SRE assistant. Answer in <= 2 sentences. "
                    "If the user asks for diagnostics tips, mention one App Service SSH alias."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=200,
        temperature=0.2,
    )
    choice = completion.choices[0]
    usage = completion.usage
    return {
        "answer": choice.message.content or "",
        "model": completion.model,
        "deployment": deployment,
        "endpoint": endpoint,
        "tokens_in": getattr(usage, "prompt_tokens", 0),
        "tokens_out": getattr(usage, "completion_tokens", 0),
        "fault_mode": faults.current_mode().value,
    }
