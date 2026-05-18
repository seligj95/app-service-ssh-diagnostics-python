"""Inline landing page — mirrors the self-heal sample's style.

Listing the SSH aliases on the home page makes the demo self-documenting: a
visitor who lands on the URL immediately sees what they're meant to do once
they SSH in.
"""

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>App Service SSH Diagnostics — Python</title>
  <style>
    body { font-family: system-ui, -apple-system, sans-serif; max-width: 820px; margin: 3rem auto; padding: 0 1.25rem; color: #1f2328; line-height: 1.55; }
    h1 { margin-bottom: 0.25rem; }
    p.lede { color: #57606a; margin-top: 0; }
    code, pre { background: #f6f8fa; border-radius: 4px; font-size: 0.92rem; }
    code { padding: 0.1rem 0.35rem; }
    pre { padding: 0.85rem 1rem; overflow-x: auto; }
    table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
    th, td { border-bottom: 1px solid #d0d7de; padding: 0.5rem 0.6rem; text-align: left; vertical-align: top; font-size: 0.93rem; }
    th { background: #f6f8fa; }
    .pill { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 0.8rem; font-weight: 600; }
    .pill.get { background: #ddf4ff; color: #0969da; }
    .pill.post { background: #dafbe1; color: #1a7f37; }
    a { color: #0969da; }
    .muted { color: #57606a; }
  </style>
</head>
<body>
  <h1>App Service SSH Diagnostics — Python</h1>
  <p class="lede">A deliberately fragile FastAPI + Azure AI Foundry app for showing off the new Python SSH helper aliases on Azure App Service for Linux.</p>

  <p>This is an API service — there's no UI. Toggle a fault below, hit <code>/chat</code>, then SSH into the app
  and walk it back to its root cause with the helpers Tulika wrote about
  <a href="https://techcommunity.microsoft.com/blog/appsonazureblog/new-ssh-helper-aliases-for-python-apps-on-azure-app-service-for-linux/4520111">here</a>.</p>

  <h2>Endpoints</h2>
  <table>
    <thead><tr><th>Method</th><th>Path</th><th>Purpose</th></tr></thead>
    <tbody>
      <tr><td><span class="pill get">GET</span></td><td><a href="/health"><code>/health</code></a></td><td>Liveness; reports current fault mode and Foundry config.</td></tr>
      <tr><td><span class="pill get">GET</span></td><td><a href="/docs"><code>/docs</code></a></td><td>Interactive OpenAPI explorer.</td></tr>
      <tr><td><span class="pill post">POST</span></td><td><code>/chat</code></td><td>Call Foundry. Body: <code>{ "prompt": "..." }</code></td></tr>
      <tr><td><span class="pill post">POST</span></td><td><code>/admin/fault</code></td><td>Toggle fault. Body: <code>{ "mode": "off|bad-creds|wrong-endpoint|dns-fail|port-mismatch|dep-import-error|latency-spike" }</code></td></tr>
      <tr><td><span class="pill get">GET</span></td><td><a href="/admin/state"><code>/admin/state</code></a></td><td>Current fault mode + the env vars the ai-* aliases will see.</td></tr>
    </tbody>
  </table>

  <h2>Try it</h2>
<pre><code># Turn the lights on
curl -X POST $URL/admin/fault \\
  -H "content-type: application/json" \\
  -d '{"mode":"off"}'

curl -X POST $URL/chat \\
  -H "content-type: application/json" \\
  -d '{"prompt":"What does the apphelp alias do?"}'

# Break it
curl -X POST $URL/admin/fault \\
  -H "content-type: application/json" \\
  -d '{"mode":"wrong-endpoint"}'

curl -X POST $URL/chat \\
  -H "content-type: application/json" \\
  -d '{"prompt":"hello"}'   # → 503</code></pre>

  <h2>Then SSH in and diagnose</h2>
<pre><code>az webapp ssh -g $RG -n $APP_NAME

# Apply whatever fault is currently active to *this* shell.
# (Toggling /admin/fault from the API only mutates the worker's env —
#  SSH shells need to source the env file to see the same broken state.)
source /home/site/diagnostics/fault.env

# Orientation
apphelp           # full alias menu
appconfig         # what env vars does the app actually see?
appenv            # full env dump (includes the AZURE_AI_* vars)
gohome            # cd /home/site
gosrc             # cd /home/site/wwwroot

# Foundry connectivity
ai-test           # auth + first-token round-trip
ai-diagnose       # all-in-one health check
ai-access-check   # MI token + RBAC
ai-dns            # endpoint DNS resolution
ai-curl           # raw HTTP probe of /models
ai-latency        # 5-call latency histogram

# App & network
applogs           # tail App Service logs
deploylogs        # last deployment output
showpkgs          # installed packages in this site's venv
checkport         # is uvicorn listening on $PORT?
appcurl /health   # hit the app from inside the container
install-nettools  # add nslookup / dig / traceroute</code></pre>

  <h2>Fault → alias map</h2>
  <table>
    <thead><tr><th>Fault</th><th>Diagnosing aliases</th></tr></thead>
    <tbody>
      <tr><td><code>bad-creds</code></td><td><code>ai-access-check</code>, <code>ai-diagnose</code>, <code>ai-test</code></td></tr>
      <tr><td><code>wrong-endpoint</code></td><td><code>ai-dns</code>, <code>ai-curl</code>, <code>ai-diagnose</code></td></tr>
      <tr><td><code>dns-fail</code></td><td><code>ai-dns</code>, <code>install-nettools</code> &rarr; <code>nslookup</code>/<code>dig</code></td></tr>
      <tr><td><code>port-mismatch</code></td><td><code>checkport</code>, <code>appcurl</code>, <code>appconfig</code></td></tr>
      <tr><td><code>dep-import-error</code></td><td><code>applogs</code>, <code>deploylogs</code>, <code>showpkgs</code></td></tr>
      <tr><td><code>latency-spike</code></td><td><code>ai-latency</code>, <code>ai-curl</code></td></tr>
    </tbody>
  </table>

  <p class="muted">Source on <a href="https://github.com/seligj95/app-service-ssh-diagnostics-python">GitHub</a>.</p>
</body>
</html>
"""
