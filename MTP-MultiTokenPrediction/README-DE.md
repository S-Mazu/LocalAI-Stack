# Gemma 4 12B — MTP-Teststack

> Windows + WSL2 + Docker · NVIDIA RTX 5080 (16 GB) · Ollama vs. llama.cpp vs. llama.cpp + MTP
> Stand: 23.08.2026

---

## 1. Beschreibung des Testsetups

Dieser Teststand misst reproduzierbar den Geschwindigkeitsgewinn von **Multi-Token Prediction
(MTP)** bei Gemma 4 12B — auf einem einzelnen NVIDIA-RTX-5080-System (16 GB VRAM) unter Windows
mit WSL2 und Docker.

Getestet werden drei Konfigurationen **desselben Modells** (Gemma 4 12B, Quantisierung Q4_K_XL):

- **llama.cpp mit MTP** — der Prüfstand.
- **llama.cpp ohne MTP** — identische Engine und Einstellungen, nur ohne Drafter. Der Vergleich
  mit dem Prüfstand isoliert den **reinen MTP-Effekt**.
- **Ollama** — dasselbe Modell in einem anderen Stack. Der Vergleich zeigt den
  **Engine-/Stack-Unterschied**, losgelöst von MTP.

Weil 16 GB VRAM nicht zwei 12B-Instanzen gleichzeitig fassen, läuft immer nur eine Engine. Der
Benchmark startet, misst und stoppt sie nacheinander automatisch und schreibt Tokens/Sekunde plus
GPU-Kennzahlen in eine CSV. Daraus ergeben sich zwei Faktoren: der **MTP-Effekt** (llama.cpp mit
vs. ohne MTP) und der **Stack-Effekt** (llama.cpp vs. Ollama).

---

## 2. Inventory — die einzurichtenden Container

| # | Container | Image | Port (Host) | Rolle |
|---|-----------|-------|-------------|-------|
| 1 | `llama-mtp` | `ghcr.io/ggml-org/llama.cpp:server-cuda` | `8080` | llama.cpp **mit** MTP — Prüfstand |
| 2 | `llama-base` | `ghcr.io/ggml-org/llama.cpp:server-cuda` | `8081` | llama.cpp **ohne** MTP — Referenz (Profil `iso`) |
| 3 | `ollama` | `ollama/ollama:latest` | `11434` | Ollama, gleiches Q4_K_XL-Modell — Stack-Vergleich |
| 4 | `open-webui` | `ghcr.io/open-webui/open-webui:main` | `3000` | gemeinsame Chat-UI — subjektiver Test |

> `llama-base` liegt im Compose-Profil `iso` und startet **nicht** im Normalbetrieb — der
> Benchmark fährt es nur für seine Referenzphase hoch und danach wieder herunter.

---

## 3. Setup — Schritte zum Einrichten

### 3.1 Windows-Host vorbereiten (einmalig)
1. **Aktuellen NVIDIA-Windows-Treiber** installieren (enthält die WSL2-CUDA-Runtime — im Container ist **kein** CUDA-Toolkit nötig).
2. **WSL2** aktivieren: in PowerShell (Admin) `wsl --install`, danach eine Ubuntu-Distribution.
3. **Docker Desktop** installieren, in den Einstellungen **WSL2-Backend** wählen und GPU-Nutzung aktivieren.

### 3.2 GPU-Durchreichung prüfen
```bash
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
```
Zeigt die Ausgabe deine RTX 5080, steht die Basis.

### 3.3 Projektordner + Modelle
Der Projektordner ist **`C:\Project\MTP-Test`** — er nimmt die Compose-Datei und **alle
persistenten Daten** auf. Zielstruktur:
```
C:\Project\MTP-Test\
├─ docker-compose.yml
├─ models\        # GGUF-Modelle (Hauptmodell + MTP-Drafter)
├─ ollama\        # Ollama-Modelle & State   (wird beim ersten Start angelegt)
└─ openwebui\     # Open-WebUI-Datenbank & Konfiguration (wird beim ersten Start angelegt)
```
**Modelle herunterladen.** Starte WSL durch Eingabe von `wsl` in PowerShell und führe dort folgende Befehle aus:
```bash
# Projektordner anlegen und hineinwechseln
mkdir -p /mnt/c/Project/MTP-Test
cd /mnt/c/Project/MTP-Test

# Download-Werkzeug installieren — Ubuntu blockt systemweites pip (PEP 668), daher pipx
sudo apt update && sudo apt install -y pipx
pipx install huggingface_hub
pipx ensurepath
```
Danach das **WSL-Terminal einmal neu öffnen** (`wsl`), damit der Befehl `hf` im PATH liegt. Dann die Modelle laden:
```bash
cd /mnt/c/Project/MTP-Test

# Hauptmodell (Q4) + MTP-Drafter nach ./models
hf download unsloth/gemma-4-12B-it-qat-GGUF \
    --local-dir ./models \
    --include "*UD-Q4_K_XL*" \
    --include "mtp-*"
```
Ergebnis in `./models`: `gemma-4-12B-it-qat-UD-Q4_K_XL.gguf` (~7 GB) + `mtp-gemma-4-12B-it.gguf` (~1 GB, Drafter).

### 3.4 `docker-compose.yml` anlegen
[`docker-compose.yml`](docker-compose.yml) aus diesem Ordner nach `C:\Project\MTP-Test\docker-compose.yml` kopieren. Alle `./`-Pfade darin sind damit
relativ zum Projektordner; die Bind-Mounts (`./models`, `./ollama`, `./openwebui`) liegen im
Projektordner und bleiben über Container-Neustarts, `docker compose down` und Image-Updates hinweg
**persistent** erhalten.

### 3.5 Stack starten
```bash
cd /mnt/c/Project/MTP-Test
docker compose pull          # immer die aktuellsten Images ziehen (überschreibt lokale Altlasten)
docker compose up -d         # startet llama-mtp, ollama, open-webui (llama-base bleibt aus)
docker compose logs -f llama-mtp   # Ladevorgang beobachten; Strg+C beendet nur die Log-Ansicht
```

### 3.6 Ollama-Modell aus derselben GGUF bauen (einmalig)
Damit Ollama exakt dieselben Gewichte wie llama.cpp fährt, wird ein Modell direkt aus der
Q4_K_XL-GGUF registriert:
```bash
cd /mnt/c/Project/MTP-Test
printf 'FROM /models/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf\n' > models/Modelfile
docker exec ollama ollama create gemma4-q4kxl -f /models/Modelfile
```
Ergebnis: das Ollama-Modell **`gemma4-q4kxl`** — es wird im Benchmark und im subjektiven Test verwendet.

### 3.7 Zugriff
- Chat-UI: `http://localhost:3000` (Modell oben im Dropdown wählen)
- llama.cpp **mit** MTP: `http://localhost:8080`
- llama.cpp **ohne** MTP: `http://localhost:8081` (nur während des Benchmarks aktiv)
- Ollama: `http://localhost:11434`

> **Wichtig:** Die MTP-Flags (`--spec-type`, `--spec-draft-n-max`, `--model-draft`) sind neu. Nach
> `docker compose pull` gegen die reale Hilfe prüfen:
> `docker run --rm ghcr.io/ggml-org/llama.cpp:server-cuda --help | grep -iE "spec|draft|mtp"`.
> **KV-Cache nicht quantisieren** (`-ctk/-ctv` weglassen) — sonst fällt die Draft-Acceptance auf 0.

---

## 4. Tests

### 4.1 Subjektiv testen
Öffne `http://localhost:3000` und schicke **denselben Prompt** nacheinander an das MTP-Modell
(llama.cpp, OpenAI-Endpoint) und an `gemma4-q4kxl` (Ollama). Achte auf die gefühlte Geschwindigkeit
und die Flüssigkeit des Textstroms. Da MTP verlustfrei ist, sollten die Antworten inhaltlich
gleichwertig sein. Für einen realistischen Eindruck einen typischen Arbeits-Prompt nehmen
(z. B. Code-Review oder eine Zusammenfassung).

### 4.2 Objektiv messen — MTP isoliert
Das Skript fährt die drei Konfigurationen **nacheinander** hoch, misst je Prompt mehrere Läufe,
protokolliert die GPU und fährt jede wieder herunter — so liegt nie mehr als ein Modell im VRAM.
Das Sampling ist über alle Engines identisch und jede erhält das Gemma-Chat-Template; die Modelle
generieren natürlich bis EOS (keine künstliche Tokengrenze). Zuerst stoppt es alle Engines, damit
kein Rest aus Schritt 3.5 mitläuft.

**Ablauf**
1. `wsl`
2. `cd /mnt/c/Project/MTP-Test`
3. `python3 -m venv ~/bench-venv`
4. `source ~/bench-venv/bin/activate`
5. `pip install requests`
6. [`bench_iso.py`](bench_iso.py) aus diesem Ordner nach `C:\Project\MTP-Test\bench_iso.py` kopieren
7. `python bench_iso.py`
8. `C:\Project\MTP-Test\mtp_benchmark.csv` in Excel öffnen

**Ergebnis lesen** — drei Labels in `mtp_benchmark.csv`, bei identischem Modell, Quant, Sampling und Chat-Template (natürliche Länge bis EOS):

- **`mtp / base`** → reiner MTP-Effekt (gleiche Engine, mit vs. ohne Drafter).
- **`base / ollama`** → Stack-Effekt (llama.cpp vs. Ollama).
- Zusätzlich je Phase **VRAM/Util/Temp/Power** — u. a. der VRAM-Aufschlag des MTP-Drafters.

Nach dem Lauf sind alle Engines gestoppt. Für den normalen Betrieb wieder `docker compose up -d` starten.

> nvidia-smi misst **GPU-weit** (inkl. Windows-Desktop), nicht nur den Container — als Trend valide,
> die absolute Modellgröße mit dem Desktop-Grundverbrauch im Hinterkopf lesen.

---

## 5. API-Liste — offene Schnittstellen im Stack

### llama.cpp (`llama-mtp` :8080, `llama-base` :8081)
OpenAI-kompatibel **plus** native Endpunkte, kein Auth per Default. `llama-base` bietet auf `:8081`
dieselben Endpunkte, läuft aber nur während des Benchmarks.

| Endpoint | Funktion |
|----------|----------|
| `POST /v1/chat/completions` | Chat-Completion (OpenAI-Format) — Haupt-Endpoint für Apps |
| `POST /v1/completions` | Klassische Text-Completion |
| `GET /v1/models` | Geladenes Modell abfragen |
| `POST /completion` | Native Completion mit `timings` (tok/s) |
| `POST /tokenize`, `/detokenize` | Text ↔ Token |
| `POST /embedding` | Embeddings (wenn aktiviert) |
| `GET /health`, `/props`, `/slots` | Status, Serverparameter, aktive Slots |
| `GET /metrics` | Prometheus-Metriken (tok/s, Latenzen) |

### Ollama (`ollama`) — `http://localhost:11434`
Native **und** OpenAI-kompatible API. Kein Auth per Default.

| Endpoint | Funktion |
|----------|----------|
| `POST /api/generate` | Native Text-Generierung |
| `POST /api/chat` | Native Chat-API (liefert `eval_count`/`eval_duration` für tok/s) |
| `POST /v1/chat/completions` | OpenAI-kompatibler Chat |
| `GET /v1/models`, `/api/tags` | Installierte Modelle auflisten |
| `POST /api/create`, `/api/show` | Modelle bauen/inspizieren |
| `GET /api/ps` | Laufende Modelle |

### Open WebUI (`open-webui`) — `http://localhost:3000`
Primär Web-Oberfläche; bietet zusätzlich eine eigene REST-API (`/api/...`) und leitet Anfragen an die Engines weiter.

> **Sicherheit:** Alle Ports hängen an `localhost`, ohne Authentifizierung. So belassen —
> nicht ungeschützt ins LAN/Internet öffnen.

---

## 6. Ressourcenliste — verwendete Websites

Alle Links in dieser Session per Fetch/Search geprüft.

**Modelle**
- Unsloth Gemma 4 12B **QAT GGUF** — hier verwendet (Q4_K_XL-Hauptmodell + `mtp-*`-Drafter): https://huggingface.co/unsloth/gemma-4-12B-it-qat-GGUF
- Unsloth Gemma 4 12B GGUF (nicht-QAT, Alternative): https://huggingface.co/unsloth/gemma-4-12b-it-GGUF
- Unsloth-Doku „How to Run MTP Models" (Flags, Download): https://unsloth.ai/docs/models/mtp

**Inferenz-Engines**
- llama.cpp Docker-Doku (Image-Tags `server-cuda` / `server-cuda13`): https://github.com/ggml-org/llama.cpp/blob/master/docs/docker.md
- llama.cpp PR #23398 „add Gemma4 MTP" (CUDA-Support, gemerged): https://github.com/ggml-org/llama.cpp/pull/23398
- llama.cpp Diskussion #22735 (Gemma4-Assistant/Drafter-Details): https://github.com/ggml-org/llama.cpp/discussions/22735
- Ollama (offizielle Seite/Registry): https://ollama.com

**UI**
- Open WebUI Quick Start (Docker, API-Anbindung): https://docs.openwebui.com/getting-started/quick-start/

**Infrastruktur (Windows/WSL2/GPU)**
- NVIDIA „CUDA on WSL" User Guide: https://docs.nvidia.com/cuda/wsl-user-guide/index.html
- Docker Desktop — GPU-Support (Windows/WSL2): https://docs.docker.com/desktop/features/gpu/

**Hintergrund MTP**
- Google „Accelerating Gemma 4 with MTP drafters": https://blog.google/innovation-and-ai/technology/developers-tools/multi-token-prediction-gemma-4/
- Google AI for Developers — Gemma MTP Overview: https://ai.google.dev/gemma/docs/mtp/overview
