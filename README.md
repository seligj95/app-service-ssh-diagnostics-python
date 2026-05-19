# App Service SSH Diagnostics — Python

> A deliberately fragile Python app, paired with the [new SSH helper aliases
> for Python apps on Azure App Service for Linux](https://techcommunity.microsoft.com/blog/appsonazureblog/new-ssh-helper-aliases-for-python-apps-on-azure-app-service-for-linux/4520111).
> Deploy it, break it on purpose, then SSH in and watch the aliases walk you
> back to the root cause.

This sample backs the blog post **"Debugging Python apps on App Service with
the new SSH helper aliases."** The repo gives you:

* A small **FastAPI app** that calls **Azure OpenAI** via managed identity
* An `/admin/fault` endpoint that toggles one of **6 realistic fault modes**
* **Bicep** infra that wires App Service + AOAI + RBAC + App Insights
* `azd up`-ready end-to-end

> **A note on Azure OpenAI vs. Azure AI Foundry.** This sample provisions an
> Azure OpenAI account (`Microsoft.CognitiveServices/accounts`, `kind: OpenAI`).
> The new `ai-*` SSH aliases speak the OpenAI chat-completions API
> (`/openai/deployments/<model>/chat/completions`), which is identical on
> Azure OpenAI and on AI Foundry projects — both expose `*.openai.azure.com`
> endpoints. The aliases work against either; the env-var name
> `AZURE_AI_FOUNDRY_ENDPOINT` is just the alias contract. If you already
> have a Foundry project, drop its endpoint into the env var and the same
> walkthrough works.

## Architecture

```
                      ┌───────────────────────────────────────┐
   curl / browser ──▶ │  App Service (Python 3.14, P0v3)      │
                      │   FastAPI                             │
                      │   ├── /            landing page       │
                      │   ├── /health                         │
                      │   ├── /chat        → AOAI via MI      │
                      │   └── /admin/fault → toggles env      │
                      └──────┬──────────────────┬─────────────┘
                             │ Managed Identity │ writes
                             ▼                  ▼
                  ┌──────────────────┐  /home/site/diagnostics/
                  │  Azure OpenAI    │  fault.env  (sourced by SSH)
                  │  gpt-4o-mini     │
                  └──────────────────┘
```

## Fault → alias map

The whole point of the sample. Two groups, and the difference matters:

### Platform-path faults — the `ai-*` aliases reproduce the failure

| Fault mode        | What breaks                              | Aliases that catch it                |
| ----------------- | ---------------------------------------- | ------------------------------------ |
| `wrong-endpoint`  | `AZURE_AI_FOUNDRY_ENDPOINT` 404s         | `ai-dns`, `ai-curl`, `ai-diagnose`   |
| `dns-fail`        | `AZURE_AI_FOUNDRY_ENDPOINT` NXDOMAIN     | `ai-dns`, `ai-curl`, `install-nettools` → `nslookup` |

### App-path faults — `ai-test` passes but your app still fails

The aliases call Foundry **directly**. If `ai-test` is green but `/chat` is
red, the divergence is in your app — its env, its dependencies, its code path.
Run `appenv`, `appconfig`, `showpkgs`, `applogs` to drill in.

| Fault mode          | What breaks                                  | Aliases that surface it            |
| ------------------- | -------------------------------------------- | ---------------------------------- |
| `bad-creds`         | `AZURE_CLIENT_ID` points at a missing UAMI   | `appenv` (envs differ), `applogs`  |
| `dep-import-error`  | App raises `ImportError` on `/chat`          | `applogs`, `deploylogs`, `showpkgs`|
| `latency-spike`     | App injects 4s before Foundry call           | `applogs` (vs. `ai-latency` clean) |
| `port-mismatch`     | `WEBSITES_PORT` ≠ uvicorn bind               | `checkport`, `appcurl`, `appconfig`|

## Quickstart

Requires `azd`, `az`, and a subscription with quota for AOAI in East US 2.

```bash
git clone https://github.com/seligj95/app-service-ssh-diagnostics-python.git
cd app-service-ssh-diagnostics-python

azd auth login
azd env new ssh-diag
azd up   # ~4 minutes
```

When `azd` finishes you'll get a URL like
`https://app-web-<token>.azurewebsites.net`. Hit `/health` to confirm.

### Drive a fault, then SSH in

```bash
URL=https://app-web-<token>.azurewebsites.net
RG=rg-ssh-diag-demo
APP=app-web-<token>

# 1) Healthy baseline
curl $URL/chat -H 'content-type: application/json' \
  -d '{"prompt":"What does the apphelp alias do?"}'

# 2) Break it
curl -X POST $URL/admin/fault -H 'content-type: application/json' \
  -d '{"mode":"wrong-endpoint"}'

curl $URL/chat -H 'content-type: application/json' \
  -d '{"prompt":"hi"}'                      # → 502

# 3) SSH in and diagnose
az webapp ssh -g $RG -n $APP

# Inside the SSH session:
source /home/site/diagnostics/fault.env     # apply active fault to this shell
apphelp                                     # all aliases at a glance
ai-diagnose                                 # one-shot Foundry health check
ai-dns                                      # see the broken DNS
ai-curl                                     # see the 6 (Could not resolve host)
```

### Fault modes

```bash
curl -X POST $URL/admin/fault -H 'content-type: application/json' \
  -d '{"mode":"off"}'                 # baseline
  -d '{"mode":"bad-creds"}'           # AZURE_CLIENT_ID = nonexistent GUID
  -d '{"mode":"wrong-endpoint"}'      # endpoint points at no-such-resource
  -d '{"mode":"dns-fail"}'            # endpoint NXDOMAIN
  -d '{"mode":"port-mismatch"}'       # WEBSITES_PORT changed under uvicorn
  -d '{"mode":"dep-import-error"}'    # /chat raises ImportError
  -d '{"mode":"latency-spike"}'       # 4s of asyncio.sleep before Foundry
```

After toggling a fault you must `source /home/site/diagnostics/fault.env` in
your SSH session — SSH shells inherit env from the container at session start,
so they don't see the app process's runtime env mutations.

## Repo layout

```
app-service-ssh-diagnostics-python/
├── main.py                  # FastAPI entrypoint
├── app/
│   ├── foundry_client.py    # AOAI / Foundry call via managed identity
│   ├── faults.py            # the 7 fault modes (off + 6)
│   └── pages.py             # inline landing page HTML
├── infra/
│   ├── main.bicep           # subscription-wired resource graph
│   ├── shared/              # plan, monitoring
│   └── app/                 # web, openai, openai-rbac
├── requirements.txt
└── azure.yaml
```

## Local dev

```bash
python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Point at an AOAI you have access to:
export AZURE_AI_FOUNDRY_ENDPOINT=https://<your-aoai>.openai.azure.com/
export AZURE_AI_MODEL=gpt-4o-mini
az login   # so DefaultAzureCredential picks up your user creds

python -m uvicorn main:app --reload --port 8000
```

Then `curl http://localhost:8000/health` and the fault endpoints work the same
way (only the `ai-*` aliases need a real App Service instance).

## Clean up

```bash
azd down --purge
```

`--purge` is important — AOAI accounts are soft-deleted by default and the
custom subdomain stays reserved unless you purge.

## License

MIT.
