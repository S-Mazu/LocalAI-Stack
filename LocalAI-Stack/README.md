# LocalAI-Stack
Documentation on how I build my local AI stack on Windows.


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
GPU Device 0: "NVIDIA GeForce RTX 5080" with compute capability …
> Compute … CUDA device: [NVIDIA GeForce RTX 5080]
```

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

`C:\Project\Local-LLM\tools\config.json`:

```json
{
  "mcpServers": {
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"],
      "env": {
        "MEMORY_FILE_PATH": "/data/memory.json"
      }
    },
    "fetch": {
      "command": "uvx",
      "args": ["mcp-server-fetch"]
    },
    "sequential-thinking": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
    },
    "everything": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-everything"]
    }
  }
}
```

### 3.5 Create the proxy configuration

`C:\Project\Local-LLM\proxy\Caddyfile`:

```
http://chat {
    reverse_proxy chat:8080
}

http://automation {
    reverse_proxy automation:5678
}

http://tools {
    reverse_proxy tools:8000
}

http://extraction {
    reverse_proxy extraction:5001
}

http://inference {
    reverse_proxy inference:11434
}
```

The `http://` prefix stops Caddy from trying to obtain certificates for these names.

### 3.6 Create docker-compose.yml

`C:\Project\Local-LLM\docker-compose.yml`:

```yaml
services:
  inference:
    container_name: inference
    image: ollama/ollama:latest
    ports: ["11434:11434"]
    volumes:
      - inference:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    restart: unless-stopped

  extraction:
    container_name: extraction
    image: ghcr.io/docling-project/docling-serve-cpu:latest
    ports: ["5001:5001"]
    environment:
      - DOCLING_SERVE_ENABLE_UI=1
    restart: unless-stopped

  tools:
    container_name: tools
    image: ghcr.io/open-webui/mcpo:main
    ports: ["8000:8000"]
    volumes:
      - ./tools:/config:ro
      - tools:/data
    command: ["--config", "/config/config.json", "--hot-reload"]
    restart: unless-stopped

  chat:
    container_name: chat
    image: ghcr.io/open-webui/open-webui:main
    ports: ["3000:8080"]
    environment:
      - OLLAMA_BASE_URL=http://inference:11434
    volumes:
      - chat:/app/backend/data
    depends_on: [inference, extraction, tools]
    restart: unless-stopped

  automation:
    container_name: automation
    image: docker.n8n.io/n8nio/n8n
    ports: ["5678:5678"]
    environment:
      - N8N_DIAGNOSTICS_ENABLED=false
      - N8N_VERSION_NOTIFICATIONS_ENABLED=false
      - EXTERNAL_FRONTEND_HOOKS_URLS=
    volumes:
      - automation:/home/node/.n8n
    restart: unless-stopped

  proxy:
    container_name: proxy
    image: caddy:latest
    ports: ["80:80"]
    volumes:
      - ./proxy:/etc/caddy
      - proxy:/data
    depends_on: [inference, chat, extraction, tools, automation]
    restart: unless-stopped

volumes:
  inference:
  chat:
  automation:
  tools:
  proxy:
```

The three `N8N_` variables turn off telemetry; without them, model calls are delayed by minutes under Windows.

### 3.7 Register names for the proxy

1. Open an editor as Administrator, open `C:\Windows\System32\drivers\etc\hosts`.
2. Append at the end:
   ```
   127.0.0.1 chat automation tools extraction inference
   ```
3. Save, then in PowerShell:
   ```powershell
   ipconfig /flushdns
   ```

Windows cannot resolve container names on its own; this entry routes them to the proxy, which picks the right container by name.

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

1. Browser: `http://chat`
2. Choose **Sign up**, enter name, email and password, submit.

The first account created gets administrator rights.

### 3.11 Set up document processing in `chat`

1. Browser: `http://chat/admin`
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
   | Hybrid Search | enabled |
   | Reranking Model | `BAAI/bge-reranker-v2-m3` |
   | Top K | `5` |
   | Top K Reranker | `20` |

4. Click **Save**.

On save, `chat` downloads the reranker model; this takes a few minutes.

### 3.12 Connect tools in `chat`

1. Browser: `http://chat/admin`
2. **Settings** tab → **Tools** entry
3. Click **+**, enter a URL, **Save** — four times, once per line:

   | URL |
   |---|
   | `http://tools:8000/memory` |
   | `http://tools:8000/fetch` |
   | `http://tools:8000/sequential-thinking` |
   | `http://tools:8000/everything` |

Each MCP server has its own path; the URL `http://tools:8000` without a path does not work.

### 3.13 Connect `automation` to the model

Workflow to build: **Chat Trigger → Basic LLM Chain → Ollama Chat Model**

1. Browser: `http://automation`, create an account.
2. Click **Create Workflow** in the top right.
3. **Add first step** → type `Chat Trigger` in the search field → click the hit. The node appears on the canvas; close the opened panel with **Back to canvas**.
4. Click the **+** to the right of the Chat Trigger node → search `Basic LLM Chain` → click it. Leave the **Prompt** field on `Take from previous node automatically`. **Back to canvas**.
5. Below the Chain node, at the **Model** connector, click **+** → search `Ollama Chat Model` → click it.
6. At **Credential to connect with**, click **Create new credential**.
7. Enter as **Base URL**: `http://inference:11434` → **Save** → close the panel.
8. Back in the Ollama node, select `qwen3.5:9b-q4_K_M` under **Model**. **Back to canvas**.
9. Click **Save** in the top right.
10. Hover over the Chat Trigger node → click **Open chat** → send `Name three colors.`

All three nodes turn green and the model's answer appears in the chat.

### 3.14 Access

| Container | Name | Port |
|---|---|---|
| `chat` | `http://chat` | `http://localhost:3000` |
| `automation` | `http://automation` | `http://localhost:5678` |
| `tools` | `http://tools/docs` | `http://localhost:8000/docs` |
| `extraction` | `http://extraction` | `http://localhost:5001` |
| `inference` | `http://inference` | `http://localhost:11434` |

`chat` and `automation` are protected by the accounts created above, the other three are not — do not expose these ports to the network.

---

## 4. Teardown

### 4.1 Remove containers, volumes and images

```powershell
cd C:\Project\Local-LLM
docker compose down -v --rmi all
```

`-v` deletes the volumes with all models, accounts and data, `--rmi all` deletes the images.

### 4.2 Remove the name entries

1. Open an editor as Administrator, open `C:\Windows\System32\drivers\etc\hosts`.
2. Delete the line `127.0.0.1 chat automation tools extraction inference`, save.
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

## 5. Links

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
- Open WebUI — Environment variables: https://docs.openwebui.com/getting-started/env-configuration/
- Open WebUI — OpenAPI tool servers: https://docs.openwebui.com/openapi-servers/open-webui/
- Open WebUI — SSO: https://docs.openwebui.com/features/sso/
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
- Docker Compose — networks and name resolution: https://docs.docker.com/compose/how-tos/networking/

**Optional**
- ComfyUI: https://docs.comfy.org/
- SearXNG: https://docs.searxng.org/
- oauth2-proxy: https://oauth2-proxy.github.io/oauth2-proxy/
- Langfuse: https://langfuse.com/self-hosting
- Portainer: https://docs.portainer.io/

---

## 6. Optional

**Capabilities**
- **ComfyUI** — image generation, reachable by the model through a tool or from `automation`.
- **SearXNG** — self-hosted metasearch as a search provider for `chat`, without an API key and without requests to third parties.

**Access**
- **oauth2-proxy** — sign in to `chat` via an existing identity provider instead of local accounts.

**Data access**
- **Docling API** — talk to `extraction` directly and fetch documents as Markdown files, independent of document search.

**Operations**
- **Langfuse** — records which text chunks were retrieved and which tools were called.
- **Portainer** — containers, logs and volumes through an interface instead of the command line.
