# Gemma 4 12B — MTP Test Stack

> Windows + WSL2 + Docker · NVIDIA RTX 5080 (16 GB) · Ollama vs. llama.cpp vs. llama.cpp + MTP
> As of: 2026-08-23

---

## 1. Description of the test setup

This test rig reproducibly measures the speed gain from **Multi-Token Prediction (MTP)** on
Gemma 4 12B — on a single NVIDIA RTX 5080 system (16 GB VRAM) under Windows with WSL2 and Docker.

Three configurations of **the same model** are tested (Gemma 4 12B, Q4_K_XL quantization):

- **llama.cpp with MTP** — the test subject.
- **llama.cpp without MTP** — identical engine and settings, just without the drafter. Comparing
  it to the test subject isolates the **pure MTP effect**.
- **Ollama** — the same model in a different stack. This comparison shows the
  **engine/stack difference**, independent of MTP.

Since 16 GB VRAM cannot hold two 12B instances at once, only one engine runs at a time. The
benchmark starts, measures and stops each one in turn automatically, writing tokens/second plus
GPU metrics to a CSV. This yields two factors: the **MTP effect** (llama.cpp with vs. without
MTP) and the **stack effect** (llama.cpp vs. Ollama).

---

## 2. Inventory — the containers to set up

| # | Container | Image | Port (Host) | Role |
|---|-----------|-------|-------------|------|
| 1 | `llama-mtp` | `ghcr.io/ggml-org/llama.cpp:server-cuda` | `8080` | llama.cpp **with** MTP — test subject |
| 2 | `llama-base` | `ghcr.io/ggml-org/llama.cpp:server-cuda` | `8081` | llama.cpp **without** MTP — reference (profile `iso`) |
| 3 | `ollama` | `ollama/ollama:latest` | `11434` | Ollama, same Q4_K_XL model — stack comparison |
| 4 | `open-webui` | `ghcr.io/open-webui/open-webui:main` | `3000` | shared chat UI — subjective test |

> `llama-base` lives in the Compose profile `iso` and does **not** start in normal operation — the
> benchmark brings it up only for its reference phase and shuts it down again afterwards.

---

## 3. Setup — steps to set it up

### 3.1 Prepare the Windows host (one-time)
1. Install the **current NVIDIA Windows driver** (includes the WSL2 CUDA runtime — **no** CUDA toolkit is needed in the container).
2. Enable **WSL2**: in PowerShell (Admin) run `wsl --install`, then an Ubuntu distribution.
3. Install **Docker Desktop**, select the **WSL2 backend** in settings and enable GPU use.

### 3.2 Verify GPU passthrough
```bash
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
```
If the output shows your RTX 5080, the base is in place.

### 3.3 Project folder + models
The project folder is **`C:\Project\MTP-Test`** — it holds the compose file and **all persistent
data**. Target structure:
```
C:\Project\MTP-Test\
├─ docker-compose.yml
├─ models\        # GGUF models (main model + MTP drafter)
├─ ollama\        # Ollama models & state   (created on first start)
└─ openwebui\     # Open WebUI database & config (created on first start)
```
**Download the models.** Start WSL by typing `wsl` in PowerShell and run the following commands there:
```bash
# Create the project folder and cd into it
mkdir -p /mnt/c/Project/MTP-Test
cd /mnt/c/Project/MTP-Test

# Install the download tool — Ubuntu blocks system-wide pip (PEP 668), hence pipx
sudo apt update && sudo apt install -y pipx
pipx install huggingface_hub
pipx ensurepath
```
Then **reopen the WSL terminal once** (`wsl`) so the `hf` command is on the PATH. Then download the models:
```bash
cd /mnt/c/Project/MTP-Test

# Main model (Q4) + MTP drafter into ./models
hf download unsloth/gemma-4-12B-it-qat-GGUF \
    --local-dir ./models \
    --include "*UD-Q4_K_XL*" \
    --include "mtp-*"
```
Result in `./models`: `gemma-4-12B-it-qat-UD-Q4_K_XL.gguf` (~7 GB) + `mtp-gemma-4-12B-it.gguf` (~1 GB, drafter).

### 3.4 Create `docker-compose.yml`
Copy [`docker-compose.yml`](docker-compose.yml) from this folder to `C:\Project\MTP-Test\docker-compose.yml`. All `./` paths in it are then relative to
the project folder; the bind mounts (`./models`, `./ollama`, `./openwebui`) live in the project
folder and stay **persistent** across container restarts, `docker compose down` and image updates.

### 3.5 Start the stack
```bash
cd /mnt/c/Project/MTP-Test
docker compose pull          # always pull the latest images (overwrites local leftovers)
docker compose up -d         # starts llama-mtp, ollama, open-webui (llama-base stays off)
docker compose logs -f llama-mtp   # watch the loading process; Ctrl+C only ends the log view
```

### 3.6 Build the Ollama model from the same GGUF (one-time)
So that Ollama runs the exact same weights as llama.cpp, a model is registered directly from the
Q4_K_XL GGUF:
```bash
cd /mnt/c/Project/MTP-Test
printf 'FROM /models/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf\n' > models/Modelfile
docker exec ollama ollama create gemma4-q4kxl -f /models/Modelfile
```
Result: the Ollama model **`gemma4-q4kxl`** — used in the benchmark and the subjective test.

### 3.7 Access
- Chat UI: `http://localhost:3000` (select the model in the dropdown at the top)
- llama.cpp **with** MTP: `http://localhost:8080`
- llama.cpp **without** MTP: `http://localhost:8081` (active only during the benchmark)
- Ollama: `http://localhost:11434`

> **Important:** The MTP flags (`--spec-type`, `--spec-draft-n-max`, `--model-draft`) are new. After
> `docker compose pull`, check them against the real help output:
> `docker run --rm ghcr.io/ggml-org/llama.cpp:server-cuda --help | grep -iE "spec|draft|mtp"`.
> **Do not quantize the KV cache** (leave out `-ctk/-ctv`) — otherwise draft acceptance drops to 0.

---

## 4. Tests

### 4.1 Subjective test
Open `http://localhost:3000` and send **the same prompt** in turn to the MTP model (llama.cpp,
OpenAI endpoint) and to `gemma4-q4kxl` (Ollama). Pay attention to the perceived speed and the
smoothness of the text stream. Since MTP is lossless, the answers should be equivalent in content.
For a realistic impression, use a typical work prompt (e.g. a code review or a summary).

### 4.2 Objective measurement — MTP isolated
The script brings the three configurations up **one after another**, measures several runs per
prompt, logs the GPU and shuts each one down again — so never more than one model sits in VRAM.
Sampling is identical across all engines and each gets the Gemma chat template; the models generate
naturally to EOS (no artificial token limit). It first stops all engines so nothing left over from
step 3.5 interferes.

**Procedure**
1. `wsl`
2. `cd /mnt/c/Project/MTP-Test`
3. `python3 -m venv ~/bench-venv`
4. `source ~/bench-venv/bin/activate`
5. `pip install requests`
6. Copy [`bench_iso.py`](bench_iso.py) from this folder to `C:\Project\MTP-Test\bench_iso.py`
7. `python bench_iso.py`
8. Open `C:\Project\MTP-Test\mtp_benchmark.csv` in Excel

**Reading the result** — three labels in `mtp_benchmark.csv`, with identical model, quant, sampling and chat template (natural length to EOS):

- **`mtp / base`** → pure MTP effect (same engine, with vs. without drafter).
- **`base / ollama`** → stack effect (llama.cpp vs. Ollama).
- Plus per phase **VRAM/util/temp/power** — among other things, the MTP drafter's VRAM overhead.

After the run, all engines are stopped. For normal operation, start `docker compose up -d` again.

> nvidia-smi measures **GPU-wide** (including the Windows desktop), not just the container — valid
> as a trend, read the absolute model size with the desktop's baseline usage in mind.

---

## 5. API list — open interfaces in the stack

### llama.cpp (`llama-mtp` :8080, `llama-base` :8081)
OpenAI-compatible **plus** native endpoints, no auth by default. `llama-base` offers the same
endpoints on `:8081`, but only runs during the benchmark.

| Endpoint | Function |
|----------|----------|
| `POST /v1/chat/completions` | Chat completion (OpenAI format) — main endpoint for apps |
| `POST /v1/completions` | Classic text completion |
| `GET /v1/models` | Query the loaded model |
| `POST /completion` | Native completion with `timings` (tok/s) |
| `POST /tokenize`, `/detokenize` | Text ↔ tokens |
| `POST /embedding` | Embeddings (if enabled) |
| `GET /health`, `/props`, `/slots` | Status, server parameters, active slots |
| `GET /metrics` | Prometheus metrics (tok/s, latencies) |

### Ollama (`ollama`) — `http://localhost:11434`
Native **and** OpenAI-compatible API. No auth by default.

| Endpoint | Function |
|----------|----------|
| `POST /api/generate` | Native text generation |
| `POST /api/chat` | Native chat API (returns `eval_count`/`eval_duration` for tok/s) |
| `POST /v1/chat/completions` | OpenAI-compatible chat |
| `GET /v1/models`, `/api/tags` | List installed models |
| `POST /api/create`, `/api/show` | Build/inspect models |
| `GET /api/ps` | Running models |

### Open WebUI (`open-webui`) — `http://localhost:3000`
Primarily a web interface; also offers its own REST API (`/api/...`) and forwards requests to the engines.

> **Security:** All ports are bound to `localhost`, without authentication. Leave it that way —
> do not expose it unprotected to the LAN/internet.

---

## 6. Resource list — websites used

All links in this session verified via fetch/search.

**Models**
- Unsloth Gemma 4 12B **QAT GGUF** — used here (Q4_K_XL main model + `mtp-*` drafter): https://huggingface.co/unsloth/gemma-4-12B-it-qat-GGUF
- Unsloth Gemma 4 12B GGUF (non-QAT, alternative): https://huggingface.co/unsloth/gemma-4-12b-it-GGUF
- Unsloth docs "How to Run MTP Models" (flags, download): https://unsloth.ai/docs/models/mtp

**Inference engines**
- llama.cpp Docker docs (image tags `server-cuda` / `server-cuda13`): https://github.com/ggml-org/llama.cpp/blob/master/docs/docker.md
- llama.cpp PR #23398 "add Gemma4 MTP" (CUDA support, merged): https://github.com/ggml-org/llama.cpp/pull/23398
- llama.cpp discussion #22735 (Gemma4 assistant/drafter details): https://github.com/ggml-org/llama.cpp/discussions/22735
- Ollama (official site/registry): https://ollama.com

**UI**
- Open WebUI Quick Start (Docker, API connection): https://docs.openwebui.com/getting-started/quick-start/

**Infrastructure (Windows/WSL2/GPU)**
- NVIDIA "CUDA on WSL" User Guide: https://docs.nvidia.com/cuda/wsl-user-guide/index.html
- Docker Desktop — GPU support (Windows/WSL2): https://docs.docker.com/desktop/features/gpu/

**MTP background**
- Google "Accelerating Gemma 4 with MTP drafters": https://blog.google/innovation-and-ai/technology/developers-tools/multi-token-prediction-gemma-4/
- Google AI for Developers — Gemma MTP Overview: https://ai.google.dev/gemma/docs/mtp/overview
