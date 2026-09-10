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
| `extraction` | `http://extraction.ai.internal/ui` | `http://localhost:5001/ui` |
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
| List `depends_on` of the `proxy` service | Add `management` |

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
docker compose restart proxy
docker logs management
```

`up -d` does not recreate `proxy` for a changed `Caddyfile`; without the restart the new name stays unrouted.

Find the line containing `setup_token=` in the output and copy the value.

**Step 5 — create an account**

1. Browser: `http://management.ai.internal`
2. Paste the **setup token**, assign a username and password — at least twelve characters — **Create user**
3. On the Edge Compute screen choose **Skip**
4. Click **Get Started**

From the container's start there are five minutes to finish step 5; after that the service inside the container shuts down. `docker restart management` restarts the window, with a new token.

The `/var/run/docker.sock` mount gives Portainer full control over the Docker engine and therefore over the machine — do not expose the interface to the network.

### 5.3 Open Terminal

Gives the model in `chat` a shell and a file system: run commands, create and edit files, install packages.

**Step 1 — uncomment the service in `docker-compose.yml`**

In [`docker-compose.yml`](docker-compose.yml), remove the comment markers in three places:

| Place | What |
|---|---|
| Block `shell:` under `services:` | The service itself |
| Entry `shell:` under `volumes:` | Its storage |
| List `depends_on` of the `proxy` service | Add `shell` |

Set `OPEN_TERMINAL_API_KEY` in the service block to a key of your choice.

The `latest` image carries roughly 4 GB of tooling — Node.js, gcc, ffmpeg, LaTeX, data-science libraries — and can install more at runtime. `ghcr.io/open-webui/open-terminal:slim` is 430 MB, holds only git, curl and jq, and cannot install anything.

**Step 2 — uncomment the block in `Caddyfile`**

In [`Caddyfile`](Caddyfile), remove the comment markers in front of the `http://shell.ai.internal` block.

**Step 3 — register the name in the hosts file**

Start an editor as Administrator, open `C:\Windows\System32\drivers\etc\hosts`, append `shell.ai.internal` to the existing line, save.

```powershell
ipconfig /flushdns
```

**Step 4 — start and check**

```powershell
cd C:\Project\Local-LLM
docker compose up -d
docker compose restart proxy
docker exec chat curl -s -o /dev/null -w "%{http_code}" http://shell:8000/docs
```

`up -d` does not recreate `proxy` for a changed `Caddyfile`; without the restart the new name stays unrouted.

The output must be:

```
200
```

**Step 5 — connect in `chat`**

1. Browser: `http://chat.ai.internal/admin`
2. **Settings** → **Integrations** → **Open Terminal** section → **+**
3. Set the values:

   | Field | Value |
   |---|---|
   | URL | `http://shell:8000` |
   | API Key | the key set in step 1 |
   | Auth Type | `Bearer` |

4. Click **Save**, then reload the page.

Without the reload the terminal does not appear in the selection in the chat.

**Step 6 — switch the model to native function calling**

1. Browser: `http://chat.ai.internal/admin`
2. **Settings** → **Models** → `qwen3.5:9b-q4_K_M` → **Advanced Params**
3. Set **Function Calling** to `Native`, **Save**.

Left on `Default`, the model never calls the terminal.

**Step 7 — test in the chat**

Open a new conversation, enable the terminal in the selection, send:

```
Create a file test.txt with the content "hello" and then show me the content.
```

The model's tool output must contain `hello`.

The documentation names a capable model as a prerequisite and lists smaller models as a reason for failure. If the test fails, it is the model, not the setup.

The shell runs in the container and sees only its file system. A mount of the Docker socket would give the model full control over the machine — it is deliberately not set.

### 5.4 InvokeAI

Generates and edits images. Standalone interface with canvas, masks and model management.

**Step 1 — get a Hugging Face access token**

The FLUX models require accepting the licence.

1. Create an account at `https://huggingface.co`.
2. Open `https://huggingface.co/black-forest-labs/FLUX.2-klein-9B`, accept the licence and the terms of use. Do the same at `https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8` — it is a separate repository with its own licence.
3. Under **Settings → Access Tokens** create a token with read permission and copy it.

**Step 2 — uncomment the service in `docker-compose.yml`**

In [`docker-compose.yml`](docker-compose.yml), remove the comment markers in three places:

| Place | What |
|---|---|
| Block `images:` under `services:` | The service itself |
| Entry `images:` under `volumes:` | Its storage |
| List `depends_on` of the `proxy` service | Add `images` |

Uncomment the `HUGGING_FACE_HUB_TOKEN` line and enter the token from step 1. Left commented out, only ungated models install.

**Step 3 — uncomment the block in `Caddyfile`**

In [`Caddyfile`](Caddyfile), remove the comment markers in front of the `http://images.ai.internal` block.

**Step 4 — register the name in the hosts file**

Start an editor as Administrator, open `C:\Windows\System32\drivers\etc\hosts`, append `images.ai.internal` to the existing line, save.

```powershell
ipconfig /flushdns
```

**Step 5 — start**

```powershell
cd C:\Project\Local-LLM
docker compose up -d
docker compose restart proxy
```

`up -d` does not recreate `proxy` for a changed `Caddyfile`; without the restart the new name stays unrouted.

Browser: `http://images.ai.internal`

**Step 6 — allow the Hugging Face CDN**

Every model install fails at once with `UnsafeDownloadURLException` until this is set:

```powershell
docker exec images sh -c "echo allow_private_download_urls: true >> /invokeai/invokeai.yaml"
docker restart images
```

Under WSL2 the Hugging Face CDN resolves over NAT64 to an address InvokeAI's SSRF guard treats as private and refuses. The setting switches that guard off.

**Step 7 — give the downloader the token**

Enter the token in the interface under **Model Manager → Add Model → HuggingFace**, then write it into the configuration as well:

```powershell
docker exec images sh -c "printf '\nremote_api_tokens:\n  - url_regex: huggingface\\\\.co\n    token: <token from step 1>\n' >> /invokeai/invokeai.yaml"
docker restart images
```

InvokeAI keeps two token stores. Installs by repo ID use the one the interface writes; installs by URL read `remote_api_tokens` and fail with `401 Unauthorized` without it.

**Step 8 — install models**

**Model Manager** tab → **Add Model** area → field for the HuggingFace repo ID. Enter one ID per row and install:

| Repo ID | Model |
|---|---|
| `black-forest-labs/FLUX.2-klein-9B` | FLUX, prompt adherence |
| `https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8/resolve/main/flux-2-klein-9b-fp8.safetensors` | The same model quantised to 8 bit, from 12 GB graphics memory |
| `Qwen/Qwen-Image` | Qwen, text inside the image |

The fp8 build is a single file, not a Diffusers folder, so it is installed by URL — a bare repo ID gives `409: No downloadable files found`. **Starter Models** lists it as **FLUX.2 Klein 9B (FP8)**.

It also needs two companions the Diffusers build carries itself. Install both, or the model cannot be used:

| Repo ID | Part |
|---|---|
| `black-forest-labs/FLUX.2-klein-4B::vae` | VAE |
| `black-forest-labs/FLUX.2-klein-9B::text_encoder+tokenizer` | Text encoder |

The download runs to several gigabytes per model. Restarting `images` pauses everything in flight; **Model Manager** resumes a paused install from its partial file.

InvokeAI loads models into graphics memory only in part and swaps during generation. This setting is on by default and makes models usable that exceed 16 GB; generation then takes longer. Unquantised `FLUX.2-klein-9B` wants around 29 GB and is the case this behaviour exists for; the fp8 variant fits without swapping and shows what the swapping costs.

**Step 9 — run the comparison**

For both models in turn with identical prompt, seed, step count and resolution:

| Task | Prompt |
|---|---|
| Prompt adherence | `three people at a table, a window on the left, daylight` |
| Text in the image | `shop sign reading "Bäckerei Mahler", street view` |

Free the graphics memory before generating:

```powershell
docker exec inference ollama stop qwen3.5:9b-q4_K_M
```

The language model reloads itself on the next request in `chat`.

**Licence:** FLUX.2 klein 9B is under the FLUX Non-Commercial License. Testing and evaluation are permitted, including by companies. Production use and generating revenue are not. The generated images may be used freely. Qwen-Image is under Apache 2.0.

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

Afterwards comment the `management` service and its volume entry back out in `docker-compose.yml`, remove `management` from the `depends_on` of the `proxy` service, comment the block in `Caddyfile` back out, and remove `management.ai.internal` from the hosts file.

```powershell
docker compose up -d
docker compose restart proxy
ipconfig /flushdns
```

### 6.3 Open Terminal

```powershell
cd C:\Project\Local-LLM
docker compose stop shell
docker compose rm -f shell
docker volume rm local-llm_shell
```

Afterwards comment the `shell` service and its volume entry back out in `docker-compose.yml`, remove `shell` from the `depends_on` of the `proxy` service, comment the block in `Caddyfile` back out, and remove `shell.ai.internal` from the hosts file. In `chat` under **Settings → Integrations → Open Terminal** delete the entry.

```powershell
docker compose up -d
docker compose restart proxy
ipconfig /flushdns
```

### 6.4 InvokeAI

```powershell
cd C:\Project\Local-LLM
docker compose stop images
docker compose rm -f images
docker volume rm local-llm_images
```

Afterwards comment the `images` service and its volume entry back out in `docker-compose.yml`, remove `images` from the `depends_on` of the `proxy` service, comment the block in `Caddyfile` back out, and remove `images.ai.internal` from the hosts file.

```powershell
docker compose up -d
docker compose restart proxy
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

**Open Terminal**
- Overview: https://docs.openwebui.com/features/open-terminal/
- Installation: https://docs.openwebui.com/features/open-terminal/setup/installation/
- Connecting to Open WebUI: https://docs.openwebui.com/features/open-terminal/setup/connecting/
- File browser: https://docs.openwebui.com/features/open-terminal/file-browser/
- Source and image variants: https://github.com/open-webui/open-terminal

**InvokeAI**
- Documentation: https://invoke.ai/
- Docker: https://invoke.ai/configuration/docker/
- System requirements: https://invoke.ai/start-here/system-requirements/
- Low-VRAM mode: https://invoke.ai/configuration/low-vram-mode/
- Installing models: https://invoke.ai/concepts/models/

**Image models**
- FLUX.2 klein — model overview: https://bfl.ai/blog/flux2-klein-towards-interactive-visual-intelligence
- FLUX.2 klein 9B — licence text: https://huggingface.co/black-forest-labs/FLUX.2-klein-9B/blob/main/LICENSE.md
- Qwen-Image — model card: https://huggingface.co/Qwen/Qwen-Image

