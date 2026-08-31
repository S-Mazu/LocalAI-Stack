# bench_iso.py — MTP-Isolationsbenchmark
#
# Faehrt ollama, llama-mtp und llama-base nacheinander hoch, misst je Prompt
# mehrere Laeufe, protokolliert die GPU und faehrt jede Engine wieder
# herunter — so liegt nie mehr als ein Modell im VRAM. Ablauf und Aufruf:
# siehe README.md Abschnitt 4.2. Ergebnis: mtp_benchmark.csv im selben Ordner.
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
