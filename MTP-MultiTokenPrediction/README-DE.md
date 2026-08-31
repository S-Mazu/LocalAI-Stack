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
Die Datei in **`C:\Project\MTP-Test\docker-compose.yml`** ablegen. Alle `./`-Pfade sind damit
relativ zum Projektordner; die Bind-Mounts (`./models`, `./ollama`, `./openwebui`) liegen im
Projektordner und bleiben über Container-Neustarts, `docker compose down` und Image-Updates hinweg
**persistent** erhalten.
```yaml
services:
  llama-mtp:                       # llama.cpp MIT MTP — Prüfstand
    container_name: llama-mtp
    image: ghcr.io/ggml-org/llama.cpp:server-cuda
    gpus: all
    ports: ["8080:8080"]
    volumes:
      - ./models:/models
    command: >
      -m /models/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf
      --model-draft /models/mtp-gemma-4-12B-it.gguf
      --spec-type draft-mtp --spec-draft-n-max 2
      -ngl 999 -fa on
      -c 8192
      --host 0.0.0.0 --port 8080
    restart: unless-stopped

  llama-base:                      # llama.cpp OHNE MTP — Referenz (nur mit --profile iso)
    container_name: llama-base
    image: ghcr.io/ggml-org/llama.cpp:server-cuda
    gpus: all
    ports: ["8081:8080"]
    volumes:
      - ./models:/models
    command: >
      -m /models/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf
      -ngl 999 -fa on
      -c 8192
      --host 0.0.0.0 --port 8080
    restart: unless-stopped
    profiles: ["iso"]

  ollama:                          # Ollama — gleiches Q4_K_XL-Modell (Stack-Vergleich)
    container_name: ollama
    image: ollama/ollama:latest
    gpus: all
    ports: ["11434:11434"]
    volumes:
      - ./ollama:/root/.ollama
      - ./models:/models:ro          # Zugriff auf dieselbe GGUF wie llama.cpp
    restart: unless-stopped

  open-webui:                      # gemeinsame Chat-UI
    container_name: open-webui
    image: ghcr.io/open-webui/open-webui:main
    ports: ["3000:8080"]
    environment:
      - OPENAI_API_BASE_URL=http://llama-mtp:8080/v1
      - OLLAMA_BASE_URL=http://ollama:11434
    volumes:
      - ./openwebui:/app/backend/data
    depends_on: [llama-mtp, ollama]
    restart: unless-stopped
```

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
6. `nano bench_iso.py` → Skript unten einfügen → `Strg+O`, `Enter`, `Strg+X`
7. `python bench_iso.py`
8. `C:\Project\MTP-Test\mtp_benchmark.csv` in Excel öffnen

**bench_iso.py**
```python
import csv, time, subprocess, statistics, threading, requests

# ---------- Konfiguration ----------
PROMPTS = {
    "code":  "Schreibe eine Funktion in Python, die Primzahlen bis N=777777 ausgibt.",
    "prosa": "Erkläre in drei Absätzen, wie ein Wankelmotor funktioniert.",
    "kurz":  "Erstelle eine Tabellede 27 EU-Mitgliedsstaaten mit Hauptstadt und Einwohnerzahl der Hauptstadt.",
    "email": "Schreibe eine herzliche Einladung zu meinem 50. Geburtstag am 1.10.2026.",
    "story": "Schreibe eine Story mit 500 Worten über Fridolin den Komposthaufen.",
}
RUNS, WARMUP, TIMEOUT, READY_TIMEOUT = 5, 1, 600, 300
OLLAMA_MODEL = "gemma4-q4kxl"                 # gleiche Q4_K_XL-GGUF wie llama.cpp
CSV = "mtp_benchmark.csv"

# Identisches Sampling über alle Engines -> fairer Vergleich.
SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 64, "seed": 42}

# Phasen in Reihenfolge. Jede: hochfahren -> bereit warten -> messen -> runterfahren.
PHASES = [
    {"engine": "ollama", "kind": "ollama",
     "up":   ["docker", "compose", "up", "-d", "ollama"],
     "down": ["docker", "compose", "stop", "ollama"],
     "ready": "http://localhost:11434/api/tags",
     "call":  "http://localhost:11434/api/chat"},
    {"engine": "mtp", "kind": "llamacpp",
     "up":   ["docker", "compose", "up", "-d", "llama-mtp"],
     "down": ["docker", "compose", "stop", "llama-mtp"],
     "ready": "http://localhost:8080/health",
     "call":  "http://localhost:8080/v1/chat/completions"},
    {"engine": "base", "kind": "llamacpp",
     "up":   ["docker", "compose", "--profile", "iso", "up", "-d", "llama-base"],
     "down": ["docker", "compose", "--profile", "iso", "stop", "llama-base"],
     "ready": "http://localhost:8081/health",
     "call":  "http://localhost:8081/v1/chat/completions"},
]

# ---------- GPU-Monitor (nvidia-smi) ----------
def _num(x):
    try: return float(x)                      # "[N/A]" (WSL2) -> None statt Absturz
    except ValueError: return None

def gpu_sample():
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.used,utilization.gpu,temperature.gpu,power.draw",
         "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.strip()
    return [_num(x) for x in out.split(",")]

class GpuMonitor(threading.Thread):          # pollt nvidia-smi im Hintergrund während der Messung
    def __init__(self, interval=0.5):
        super().__init__(daemon=True)
        self.interval, self.samples, self._halt = interval, [], threading.Event()
    def run(self):
        while not self._halt.is_set():
            try: self.samples.append(gpu_sample())
            except Exception: pass
            time.sleep(self.interval)
    def stop(self):
        self._halt.set(); self.join()
    def summary(self):
        def vals(i): return [s[i] for s in self.samples if s[i] is not None]
        m, u, t, p = vals(0), vals(1), vals(2), vals(3)   # VRAM bleibt, auch wenn Temp/Power N/A
        return {"vram_mb_max": round(max(m)) if m else "",
                "gpu_util_avg": round(sum(u) / len(u), 1) if u else "",
                "temp_c_max":  round(max(t)) if t else "",
                "power_w_avg": round(sum(p) / len(p), 1) if p else ""}

# ---------- Hilfsfunktionen ----------
def run(cmd):
    print("$", " ".join(cmd)); subprocess.run(cmd, check=True)

def wait_ready(url):                          # wartet, bis der Server 200 liefert (Modell geladen)
    print(f"   warte auf {url} …", end="", flush=True)
    start = time.perf_counter()
    while time.perf_counter() - start < READY_TIMEOUT:
        try:
            if requests.get(url, timeout=5).status_code == 200:
                print(" bereit"); return
        except requests.RequestException:
            pass
        time.sleep(2)
    raise TimeoutError(f"Server nicht bereit: {url}")

def measure(phase, prompt):                   # ein Aufruf -> tok/s aus der Antwort
    t0 = time.perf_counter()
    if phase["kind"] == "llamacpp":
        # Chat-Endpunkt: Server wendet Gemmas Template an, tokenisiert Spezialtokens korrekt,
        # setzt den Stop selbst und liefert timings mit.
        payload = {"messages": [{"role": "user", "content": prompt}], "stream": False,
                   "chat_template_kwargs": {"enable_thinking": False},  # Thinking aus, wie bei Ollama
                   **SAMPLING}
        r = requests.post(phase["call"], json=payload, timeout=TIMEOUT).json()
        t = r["timings"]
        gen = t.get("predicted_per_second", 0.0)
        pr  = t.get("prompt_per_second", 0.0)
        ntok = r["usage"]["completion_tokens"]
        text = r["choices"][0]["message"]["content"]
    else:
        payload = {"model": OLLAMA_MODEL, "stream": False, "think": False,
                   "messages": [{"role": "user", "content": prompt}],
                   "options": {"num_predict": -1, **SAMPLING}}
        r = requests.post(phase["call"], json=payload, timeout=TIMEOUT).json()
        ec, ed   = r.get("eval_count", 0), r.get("eval_duration", 0)
        pec, ped = r.get("prompt_eval_count", 0), r.get("prompt_eval_duration", 0)
        gen  = ec / (ed / 1e9) if ed else 0.0          # ed=0 bei Prompt-Cache-Hit abfangen
        pr   = pec / (ped / 1e9) if ped else 0.0
        ntok = ec
        text = r.get("message", {}).get("content", "")  # generierter Text
    return {"gen_tok_s": round(gen, 2), "prompt_tok_s": round(pr, 2),
            "gen_tokens": ntok, "wall_s": round(time.perf_counter() - t0, 3),
            "output": text}

# ---------- Ablauf ----------
# Sauberer Start: alle Engines aus (open-webui darf laufen, nutzt keine GPU).
subprocess.run(["docker", "compose", "stop", "llama-mtp", "ollama"])
subprocess.run(["docker", "compose", "--profile", "iso", "stop", "llama-base"])

rows = []
for phase in PHASES:
    print(f"\n=== Phase: {phase['engine']} ===")
    run(phase["up"])
    try:
        wait_ready(phase["ready"])
        for _ in range(WARMUP):
            measure(phase, next(iter(PROMPTS.values())))  # Warmup: Modell in den VRAM laden
        mon = GpuMonitor(); mon.start()                  # GPU während der Messung protokollieren
        phase_rows = []
        for label, prompt in PROMPTS.items():
            for i in range(1, RUNS + 1):
                m = measure(phase, prompt)
                m.update({"prompt": label, "engine": phase["engine"], "run": i})
                phase_rows.append(m)
                print(f'{label:>5} | {phase["engine"]:>6} | Lauf {i:>2}: {m["gen_tok_s"]:>7} tok/s')
        mon.stop()
        gpu = mon.summary()
        for m in phase_rows:                             # GPU-Kennzahlen an jede Zeile hängen
            m.update(gpu)
        rows.extend(phase_rows)
        print(f'   GPU: {gpu["vram_mb_max"]} MB (max) | {gpu["gpu_util_avg"]} % | '
              f'{gpu["temp_c_max"]} °C | {gpu["power_w_avg"]} W')
    finally:
        run(phase["down"])                               # immer runterfahren -> VRAM frei

# ---------- CSV ----------
fields = ["prompt", "engine", "run", "gen_tok_s", "prompt_tok_s", "gen_tokens", "wall_s",
          "vram_mb_max", "gpu_util_avg", "temp_c_max", "power_w_avg", "output"]
with open(CSV, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)

# ---------- Auswertung ----------
print("\n--- Ergebnis (Ø Generation tok/s) ---")
for label in PROMPTS:
    mean = {}
    for engine in ("ollama", "mtp", "base"):
        v = [r["gen_tok_s"] for r in rows if r["engine"] == engine and r["prompt"] == label]
        if v:
            mean[engine] = statistics.mean(v)
            print(f'{label:>5} | {engine:>6}: {mean[engine]:6.1f}  (σ {statistics.pstdev(v):.1f})')
    if "base" in mean and "mtp" in mean:
        print(f'{label:>5} | reiner MTP-Effekt   (mtp/base):        {mean["mtp"] / mean["base"]:.2f}x')
    if "ollama" in mean and "base" in mean:
        print(f'{label:>5} | Stack llama.cpp/Ollama (base/ollama):  {mean["base"] / mean["ollama"]:.2f}x\n')
```

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
