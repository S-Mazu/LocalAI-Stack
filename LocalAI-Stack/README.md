# Local LLM Stack — How-To

> Created by Stefan Mazur with Claude Opus 5, as of 2026-08-28

---

## 1. What the stack does

A fully local AI workspace: chat with a language model that can access your own documents and call tools — without any data leaving the machine.

`inference` runs the language model on the GPU. `chat` is the interface and hosts document search: uploaded PDFs are broken down into structured text by `extraction`, split into chunks, turned into vectors by an embedding model, and searched on every question. A reranker then sorts the hits by actual relevance. Through `tools`, the model reaches MCP tools — memory, web fetch, structured thinking. `automation` drives workflows that run without a user in the chat.

---

## 2. Container inventory

| # | Container | Product | Image | Port | Role |
|---|-----------|---------|-------|------|------|
| 1 | `inference` | Ollama | `ollama/ollama:latest` | `11434` | Language and embedding model, GPU |
| 2 | `chat` | Open WebUI | `ghcr.io/open-webui/open-webui:main` | `3000` | Interface, RAG, reranking |
| 3 | `extraction` | Docling | `ghcr.io/docling-project/docling-serve-cpu` | `5001` | Document extraction |
| 4 | `tools` | mcpo | `ghcr.io/open-webui/mcpo:main` | `8000` | MCP → OpenAPI |
| 5 | `automation` | n8n | `docker.n8n.io/n8nio/n8n` | `5678` | Orchestration |
| 6 | `proxy` | Caddy | `caddy:latest` | `80` | Reachability by name instead of ports |

---

## 3. Setup

### 3.1 Prepare Windows (one-time)

1. Install the current **NVIDIA Windows driver**: https://www.nvidia.com/en-us/drivers/
2. Open PowerShell as Administrator, install **WSL2**:
   ```powershell
   wsl --install --no-distribution
   wsl --update
   ```
3. Restart Windows.
4. Download **Docker Desktop**: https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe
5. Double-click `Docker Desktop Installer.exe`, go through the wizard, then restart Windows.
6. Open Docker Desktop → click the **Settings** icon in the dashboard → **General** tab → **Use the WSL 2 based engine** must be enabled.

### 3.2 Verify GPU passthrough

```powershell
docker run --rm -it --gpus=all nvcr.io/nvidia/k8s/cuda-sample:nbody nbody -gpu -benchmark
```

The output must name the card:

```
> Compute 12.0 CUDA device: [NVIDIA GeForce RTX 5080 Laptop GPU]
```

The line above it names the architecture, not the card, and can be outdated — the CUDA sample does not know Blackwell and reports "Ampere".

Remove the test image afterwards:

```powershell
docker rmi nvcr.io/nvidia/k8s/cuda-sample:nbody
```

### 3.3 Create the project folder

PowerShell:

```powershell
mkdir C:\Project\Local-LLM\tools
mkdir C:\Project\Local-LLM\proxy
cd C:\Project\Local-LLM
```

Target structure:
```
C:\Project\Local-LLM\
├─ docker-compose.yml
├─ proxy\Caddyfile
└─ tools\config.json
```

### 3.4 Create the MCP configuration

Copy [`config.json`](config.json) from this folder to `C:\Project\Local-LLM\tools\config.json`.

### 3.5 Create the proxy configuration

Copy [`Caddyfile`](Caddyfile) from this folder to `C:\Project\Local-LLM\proxy\Caddyfile`.

The `http://` prefix in it stops Caddy from trying to obtain certificates for these names.

### 3.6 Create docker-compose.yml

Copy [`docker-compose.yml`](docker-compose.yml) from this folder to `C:\Project\Local-LLM\docker-compose.yml`.

The three `N8N_` variables in it switch telemetry off; without them model calls on Windows are delayed by minutes.

### 3.7 Register names for the proxy

1. Start an editor as Administrator, open `C:\Windows\System32\drivers\etc\hosts`.
2. Append at the end:
   ```
   127.0.0.1 chat.ai.internal automation.ai.internal tools.ai.internal extraction.ai.internal inference.ai.internal
   ```
3. Save, then in PowerShell:
   ```powershell
   ipconfig /flushdns
   ```

Windows cannot resolve container names on its own; this entry forwards them to the proxy, which picks the right container by name.

### 3.8 Start the stack

```powershell
cd C:\Project\Local-LLM
docker compose pull
docker compose up -d
docker compose ps
```

### 3.9 Load models into `inference`

```powershell
docker exec inference ollama pull qwen3.5:9b-q4_K_M
docker exec inference ollama pull qwen3-embedding:8b
docker exec inference ollama list
```

### 3.10 Create an account in `chat`

1. Browser: `http://chat.ai.internal`
2. Choose **Sign up**, enter name, e-mail and password, submit.

The first account created gets administrator rights.

### 3.11 Set up document processing in `chat`

1. Browser: `http://chat.ai.internal/admin`
2. **Settings** tab → **Documents** entry
3. Set the values:

   | Field | Value |
   |---|---|
   | Content Extraction Engine | `Docling` |
   | Docling Server URL | `http://extraction:5001` |
   | Embedding Model Engine | `Ollama` |
   | Ollama Base URL | `http://inference:11434` |
   | Embedding Model | `qwen3-embedding:8b` |
   | Chunk Size | `512` |
   | Chunk Overlap | `50` |
   | Embedding Batch Size | `32` |
   | Hybrid Search | enabled |
   | Reranking Model | `BAAI/bge-reranker-v2-m3` |
   | Top K | `5` |
   | Top K Reranker | `20` |

4. Click **Save**.

On save, `chat` downloads the reranker model; that takes a few minutes.

### 3.12 Connect tools in `chat`

1. Browser: `http://chat.ai.internal/admin`
2. **Settings** tab → **Integrations** entry → **External Tool Servers** section
3. Click **+** on the right, enter one URL, **Save** — four times, once per row:

   | URL |
   |---|
   | `http://tools:8000/memory` |
   | `http://tools:8000/fetch` |
   | `http://tools:8000/sequential-thinking` |
   | `http://tools:8000/everything` |

Every MCP server has its own path; the URL `http://tools:8000` without a path does not work.

### 3.13 Connect `automation` to the model

Workflow to build: **Chat Trigger → Basic LLM Chain → Ollama Chat Model**

1. Browser: `http://automation.ai.internal`, create an account.
2. Click **Create Workflow** at the top right.
3. **Add first step** → type `Chat Trigger` in the search field → click the hit. The node appears on the canvas; close the opened window with **Back to canvas**.
4. Click the **+** on the right of the Chat Trigger node → search `Basic LLM Chain` → click it. Leave the **Prompt** field on `Take from previous node automatically`. **Back to canvas**.
5. Below the Chain node, click **+** on the **Model** connector → search `Ollama Chat Model` → click it.
6. At **Credential to connect with** click **Create new credential**.
7. Enter as **Base URL**: `http://inference:11434` → **Save** → close the window.
8. Back in the Ollama node, select `qwen3.5:9b-q4_K_M` at **Model**. **Back to canvas**.
9. Click **Save** at the top right.
10. Hover the Chat Trigger node → click **Open chat** → send `Name three colours.`

All three nodes turn green and the model's answer appears in the chat.

### 3.14 Access

| Container | Name | Port |
|---|---|---|
| `chat` | `http://chat.ai.internal` | `http://localhost:3000` |
| `automation` | `http://automation.ai.internal` | `http://localhost:5678` |
| `tools` | `http://tools.ai.internal/docs` | `http://localhost:8000/docs` |
| `extraction` | `http://extraction.ai.internal` | `http://localhost:5001` |
| `inference` | `http://inference.ai.internal` | `http://localhost:11434` |

`chat` and `automation` are protected by the accounts created, the other three are not — do not expose those ports to the network.

---

## 4. Teardown

### 4.1 Remove containers, volumes and images

```powershell
cd C:\Project\Local-LLM
docker compose down -v --rmi all
```

`-v` deletes the volumes with all models, accounts and data, `--rmi all` the images.

### 4.2 Remove the name entries

1. Start an editor as Administrator, open `C:\Windows\System32\drivers\etc\hosts`.
2. Delete the line `127.0.0.1 chat.ai.internal automation.ai.internal tools.ai.internal extraction.ai.internal inference.ai.internal`, save.
3. In PowerShell:
   ```powershell
   ipconfig /flushdns
   ```

### 4.3 Delete the project folder

```powershell
cd C:\
Remove-Item -Recurse -Force C:\Project\Local-LLM
```

### 4.4 Uninstall Docker Desktop

1. **Settings → Apps → Installed apps → Docker Desktop → Uninstall**
2. After uninstalling, delete these directories:
   ```
   C:\ProgramData\Docker
   C:\ProgramData\DockerDesktop
   C:\Program Files\Docker
   %LOCALAPPDATA%\Docker
   %APPDATA%\Docker
   %APPDATA%\Docker Desktop
   %USERPROFILE%\.docker
   ```

---

## 5. Optional

### 5.1 Docling API

Converts files to Markdown, independently of document search. There is nothing to install — `extraction` is already running.

**Way 1 — interface**

1. Browser: `http://extraction.ai.internal/ui`
2. Drag a file in, choose output format **md**, convert, download the result.

**Way 2 — command line**

PowerShell in the folder holding the source file:

```powershell
$response = curl.exe -s -X POST http://extraction.ai.internal/v1/convert/file `
  -F "files=@document.pdf;type=application/pdf" `
  -F "to_formats=md" | ConvertFrom-Json
$response.document.md_content | Out-File -Encoding utf8 document.md
```

`curl.exe` must be written with the extension — `curl` alone is a different command in PowerShell.

All endpoints and options: `http://extraction.ai.internal/docs`

### 5.2 Portainer

Interface for managing all containers: status, logs, console, restart, resource usage. Replaces the PowerShell commands from section 3.

**Step 1 — uncomment the service in `docker-compose.yml`**

In [`docker-compose.yml`](docker-compose.yml), remove the comment markers in three places:

| Place | What |
|---|---|
| Block `management:` under `services:` | The service itself |
| Entry `management:` under `volumes:` | Its storage |
| Second `depends_on` line of the `proxy` service | The variant with `management`; comment out the first one |

Without the `--http-enabled` switch Portainer serves HTTPS on port 9443 only.

**Step 2 — uncomment the block in `Caddyfile`**

In [`Caddyfile`](Caddyfile), remove the comment markers in front of the `http://management.ai.internal` block.

**Step 3 — register the name in the hosts file**

Start an editor as Administrator, open `C:\Windows\System32\drivers\etc\hosts`, append `management.ai.internal` to the existing line, save.

```powershell
ipconfig /flushdns
```

**Step 4 — start and fetch the setup token**

```powershell
cd C:\Project\Local-LLM
docker compose up -d
docker logs management
```

Find the line containing `setup_token=` in the output and copy the value.

**Step 5 — create an account**

1. Browser: `http://management.ai.internal`
2. Paste the **setup token**, assign a username and password — at least twelve characters — **Create user**
3. On the Edge Compute screen choose **Skip**
4. Click **Get Started**

From the container's start there are five minutes to finish step 5; after that the service inside the container shuts down. `docker restart management` restarts the window, with a new token.

The `/var/run/docker.sock` mount gives Portainer full control over the Docker engine and therefore over the machine — do not expose the interface to the network.

---

## 6. Teardown Optional

### 6.1 Docling API

Delete the generated Markdown files:

```powershell
Remove-Item *.md
```

There is nothing to tear down on the stack itself: the API belongs to the already present `extraction` container.

### 6.2 Portainer

```powershell
cd C:\Project\Local-LLM
docker compose stop management
docker compose rm -f management
docker volume rm local-llm_management
```

Afterwards comment the `management` service, its volume entry and the `depends_on` variant with `management` back out in `docker-compose.yml`, comment the block in `Caddyfile` back out, and remove `management.ai.internal` from the hosts file.

```powershell
docker compose up -d
ipconfig /flushdns
```

---

## 7. Links

**Models**
- Qwen3.5 (Ollama): https://ollama.com/library/qwen3.5
- Qwen3-Embedding (Ollama): https://ollama.com/library/qwen3-embedding
- BGE-Reranker-v2-m3: https://huggingface.co/BAAI/bge-reranker-v2-m3

**Containers**
- Ollama: https://ollama.com
- Open WebUI: https://docs.openwebui.com
- Docling-Serve: https://github.com/docling-project/docling-serve
- mcpo: https://github.com/open-webui/mcpo
- n8n: https://docs.n8n.io
- Caddy: https://caddyserver.com/docs/

**MCP servers**
- Reference servers: https://github.com/modelcontextprotocol/servers
- Memory (incl. `MEMORY_FILE_PATH`): https://www.npmjs.com/package/@modelcontextprotocol/server-memory
- Fetch: https://github.com/modelcontextprotocol/servers/tree/main/src/fetch
- Sequential Thinking: https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking
- Everything: https://github.com/modelcontextprotocol/servers/tree/main/src/everything

**Configuration**
- Open WebUI — RAG: https://docs.openwebui.com/features/chat-conversations/rag/
- Open WebUI — Docling: https://docs.openwebui.com/features/chat-conversations/rag/document-extraction/docling/
- Open WebUI — Tools: https://docs.openwebui.com/features/extensibility/plugin/tools/
- Open WebUI — environment variables: https://docs.openwebui.com/getting-started/env-configuration/
- Open WebUI — OpenAPI tool servers: https://docs.openwebui.com/openapi-servers/open-webui/
- Docker Compose — GPU support: https://docs.docker.com/compose/how-tos/gpu-support/
- Caddy — Caddyfile tutorial: https://caddyserver.com/docs/caddyfile-tutorial
- Caddy — `reverse_proxy` directive: https://caddyserver.com/docs/caddyfile/directives/reverse_proxy
- Caddy — Docker image: https://hub.docker.com/_/caddy
- n8n — Ollama credential: https://docs.n8n.io/integrations/builtin/credentials/ollama/
- n8n — Ollama Model node, known issues: https://docs.n8n.io/integrations/builtin/cluster-nodes/sub-nodes/n8n-nodes-langchain.lmollama/common-issues/
- n8n — Chat Trigger: https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-langchain.chattrigger/
- n8n — Basic LLM Chain: https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.chainllm

**Infrastructure**
- NVIDIA CUDA on WSL: https://docs.nvidia.com/cuda/wsl-user-guide/index.html
- Docker Desktop GPU support: https://docs.docker.com/desktop/features/gpu/
- Docker Desktop WSL: https://docs.docker.com/desktop/features/wsl/
- Docker Desktop Windows — installation: https://docs.docker.com/desktop/setup/install/windows-install/
- Docker Desktop — settings: https://docs.docker.com/desktop/settings-and-maintenance/settings/
- WSL — commands and options: https://learn.microsoft.com/en-us/windows/wsl/basic-commands
- Docker Compose — networking and name resolution: https://docs.docker.com/compose/how-tos/networking/

**Docling**
- Docling: https://docling-project.github.io/docling/
- Docling-Serve — API usage: https://github.com/docling-project/docling-serve/blob/main/docs/usage.md

**Portainer**
- Installation on WSL / Docker Desktop: https://docs.portainer.io/start/install-ce/server/docker/wsl
- Initial setup: https://docs.portainer.io/start/install-ce/server/setup
- Finding, skipping and adjusting the setup token: https://docs.portainer.io/faqs/installing/setup-token
- CLI switches: https://docs.portainer.io/advanced/cli
- Five-minute window: https://docs.portainer.io/faqs/installing/your-portainer-instance-has-timed-out-for-security-purposes-error-fix
