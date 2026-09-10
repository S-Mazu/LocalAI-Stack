# Local LLM Stack — How-To

> Erstellt durch Stefan Mazur mit Claude Opus 5, Stand 28.08.2026

---

## 1. Was der Stack tut

Ein vollständig lokaler KI-Arbeitsplatz: Chat mit einem Sprachmodell, das auf eigene Dokumente zugreift und Werkzeuge aufrufen kann — ohne dass Daten den Rechner verlassen.

`inference` führt das Sprachmodell auf der GPU aus. `chat` ist die Oberfläche und beherbergt die Dokumentensuche: Hochgeladene PDFs werden von `extraction` in strukturierten Text zerlegt, in Abschnitte geteilt, von einem Embedding-Modell in Vektoren umgewandelt und bei jeder Frage durchsucht. Ein Reranker sortiert die Treffer nach echter Relevanz nach. Über `tools` erreicht das Modell MCP-Werkzeuge — Gedächtnis, Webabruf, strukturiertes Denken. `automation` steuert Abläufe, die ohne Nutzer im Chat laufen sollen.

---

## 2. Container-Inventar

| # | Container | Produkt | Image | Port | Rolle |
|---|-----------|---------|-------|------|-------|
| 1 | `inference` | Ollama | `ollama/ollama:latest` | `11434` | Sprach- und Embedding-Modell, GPU |
| 2 | `chat` | Open WebUI | `ghcr.io/open-webui/open-webui:main` | `3000` | Oberfläche, RAG, Reranking |
| 3 | `extraction` | Docling | `ghcr.io/docling-project/docling-serve-cpu` | `5001` | Dokument-Extraktion |
| 4 | `tools` | mcpo | `ghcr.io/open-webui/mcpo:main` | `8000` | MCP → OpenAPI |
| 5 | `automation` | n8n | `docker.n8n.io/n8nio/n8n` | `5678` | Orchestrierung |
| 6 | `proxy` | Caddy | `caddy:latest` | `80` | Erreichbarkeit über Namen statt Ports |

---

## 3. Setup

### 3.1 Windows vorbereiten (einmalig)

1. Aktuellen **NVIDIA-Windows-Treiber** installieren: https://www.nvidia.com/en-us/drivers/
2. PowerShell als Administrator öffnen, **WSL2** installieren:
   ```powershell
   wsl --install --no-distribution
   wsl --update
   ```
3. Windows neu starten.
4. **Docker Desktop** herunterladen: https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe
5. `Docker Desktop Installer.exe` per Doppelklick starten, Assistenten durchlaufen, danach Windows neu starten.
6. Docker Desktop öffnen → im Dashboard das **Settings**-Symbol anklicken → Reiter **General** → **Use the WSL 2 based engine** muss aktiv sein.

### 3.2 GPU-Durchreichung prüfen

```powershell
docker run --rm -it --gpus=all nvcr.io/nvidia/k8s/cuda-sample:nbody nbody -gpu -benchmark
```

In der Ausgabe muss die Karte namentlich erscheinen:

```
> Compute 12.0 CUDA device: [NVIDIA GeForce RTX 5080 Laptop GPU]
```

Die Zeile darüber nennt die Architektur, nicht die Karte, und kann veraltet sein — das CUDA-Sample kennt Blackwell nicht und meldet „Ampere".

Test-Image danach entfernen:

```powershell
docker rmi nvcr.io/nvidia/k8s/cuda-sample:nbody
```

### 3.3 Projektordner anlegen

PowerShell:

```powershell
mkdir C:\Project\Local-LLM\tools
mkdir C:\Project\Local-LLM\proxy
cd C:\Project\Local-LLM
```

Zielstruktur:
```
C:\Project\Local-LLM\
├─ docker-compose.yml
├─ proxy\Caddyfile
└─ tools\config.json
```

### 3.4 MCP-Konfiguration anlegen

[`config.json`](config.json) aus diesem Ordner nach `C:\Project\Local-LLM\tools\config.json` kopieren.

### 3.5 Proxy-Konfiguration anlegen

[`Caddyfile`](Caddyfile) aus diesem Ordner nach `C:\Project\Local-LLM\proxy\Caddyfile` kopieren.

Das Präfix `http://` darin verhindert, dass Caddy für diese Namen Zertifikate zu beschaffen versucht.

### 3.6 docker-compose.yml anlegen

[`docker-compose.yml`](docker-compose.yml) aus diesem Ordner nach `C:\Project\Local-LLM\docker-compose.yml` kopieren.

Die drei `N8N_`-Variablen darin schalten Telemetrie ab; ohne sie verzögern sich Modellaufrufe unter Windows um Minuten.

### 3.7 Namen für den Proxy eintragen

1. Editor als Administrator starten, `C:\Windows\System32\drivers\etc\hosts` öffnen.
2. Am Ende anhängen:
   ```
   127.0.0.1 chat.ai.internal automation.ai.internal tools.ai.internal extraction.ai.internal inference.ai.internal
   ```
3. Speichern, dann in PowerShell:
   ```powershell
   ipconfig /flushdns
   ```

Windows kann Container-Namen nicht selbst auflösen; dieser Eintrag leitet sie an den Proxy weiter, der anhand des Namens den richtigen Container auswählt.

### 3.8 Stack starten

```powershell
cd C:\Project\Local-LLM
docker compose pull
docker compose up -d
docker compose ps
```

### 3.9 Modelle in `inference` laden

```powershell
docker exec inference ollama pull qwen3.5:9b-q4_K_M
docker exec inference ollama pull qwen3-embedding:8b
docker exec inference ollama list
```

### 3.10 Konto in `chat` anlegen

1. Browser: `http://chat.ai.internal`
2. **Sign up** wählen, Name, E-Mail und Passwort eintragen, absenden.

Das erste angelegte Konto erhält Administratorrechte.

### 3.11 Dokumentverarbeitung in `chat` einrichten

1. Browser: `http://chat.ai.internal/admin`
2. Reiter **Settings** → Eintrag **Documents**
3. Werte setzen:

   | Feld | Wert |
   |---|---|
   | Content Extraction Engine | `Docling` |
   | Docling Server URL | `http://extraction:5001` |
   | Embedding Model Engine | `Ollama` |
   | Ollama Base URL | `http://inference:11434` |
   | Embedding Model | `qwen3-embedding:8b` |
   | Chunk Size | `512` |
   | Chunk Overlap | `50` |
   | Embedding Batch Size | `32` |
   | Hybrid Search | eingeschaltet |
   | Reranking Model | `BAAI/bge-reranker-v2-m3` |
   | Top K | `5` |
   | Top K Reranker | `20` |

4. **Save** klicken.

Beim Speichern lädt `chat` das Reranker-Modell herunter; das dauert einige Minuten.

### 3.12 Werkzeuge in `chat` anbinden

1. Browser: `http://chat.ai.internal/admin`
2. Reiter **Settings** → Eintrag **Integrations** → Abschnitt **External Tool Servers**
3. Rechts auf **+** klicken, eine URL eintragen, **Save** — vier Mal, je Zeile einmal:

   | URL |
   |---|
   | `http://tools:8000/memory` |
   | `http://tools:8000/fetch` |
   | `http://tools:8000/sequential-thinking` |
   | `http://tools:8000/everything` |

Jeder MCP-Server hat einen eigenen Pfad; die URL `http://tools:8000` ohne Pfad funktioniert nicht.

### 3.13 `automation` mit dem Modell verbinden

Aufzubauender Workflow: **Chat Trigger → Basic LLM Chain → Ollama Chat Model**

1. Browser: `http://automation.ai.internal`, Konto anlegen.
2. Oben rechts **Create Workflow** klicken.
3. **Add first step** → im Suchfeld `Chat Trigger` eingeben → Treffer anklicken. Der Node erscheint auf der Arbeitsfläche; das geöffnete Fenster mit **Back to canvas** schließen.
4. Auf das **+** rechts am Chat-Trigger-Node klicken → `Basic LLM Chain` suchen → anklicken. Feld **Prompt** auf `Take from previous node automatically` stehen lassen. **Back to canvas**.
5. Unterhalb des Chain-Nodes am Anschluss **Model** auf **+** klicken → `Ollama Chat Model` suchen → anklicken.
6. Bei **Credential to connect with** auf **Create new credential** klicken.
7. Als **Base URL** eintragen: `http://inference:11434` → **Save** → Fenster schließen.
8. Zurück im Ollama-Node bei **Model** `qwen3.5:9b-q4_K_M` auswählen. **Back to canvas**.
9. Oben rechts **Save** klicken.
10. Auf den Chat-Trigger-Node zeigen → **Open chat** klicken → `Nenne drei Farben.` senden.

Alle drei Nodes werden grün und im Chat steht die Antwort des Modells.

### 3.14 Zugriff

| Container | Name | Port |
|---|---|---|
| `chat` | `http://chat.ai.internal` | `http://localhost:3000` |
| `automation` | `http://automation.ai.internal` | `http://localhost:5678` |
| `tools` | `http://tools.ai.internal/docs` | `http://localhost:8000/docs` |
| `extraction` | `http://extraction.ai.internal/ui` | `http://localhost:5001/ui` |
| `inference` | `http://inference.ai.internal` | `http://localhost:11434` |

`chat` und `automation` sind durch die angelegten Konten geschützt, die übrigen drei nicht — die Ports nicht ins Netzwerk freigeben.

---

## 4. Rückbau

### 4.1 Container, Volumes und Images entfernen

```powershell
cd C:\Project\Local-LLM
docker compose down -v --rmi all
```

`-v` löscht die Volumes mit allen Modellen, Konten und Daten, `--rmi all` die Images.

### 4.2 Namenseinträge entfernen

1. Editor als Administrator starten, `C:\Windows\System32\drivers\etc\hosts` öffnen.
2. Zeile `127.0.0.1 chat.ai.internal automation.ai.internal tools.ai.internal extraction.ai.internal inference.ai.internal` löschen, speichern.
3. In PowerShell:
   ```powershell
   ipconfig /flushdns
   ```

### 4.3 Projektordner löschen

```powershell
cd C:\
Remove-Item -Recurse -Force C:\Project\Local-LLM
```

### 4.4 Docker Desktop deinstallieren

1. **Einstellungen → Apps → Installierte Apps → Docker Desktop → Deinstallieren**
2. Nach der Deinstallation diese Verzeichnisse löschen:
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

### 5.1 Docling-API

Wandelt Dateien in Markdown um, unabhängig von der Dokumentensuche. Es ist nichts zu installieren — `extraction` läuft bereits.

**Weg 1 — Oberfläche**

1. Browser: `http://extraction.ai.internal/ui`
2. Datei hineinziehen, Ausgabeformat **md** wählen, umwandeln, Ergebnis herunterladen.

**Weg 2 — Kommandozeile**

PowerShell im Ordner mit der Quelldatei:

```powershell
$antwort = curl.exe -s -X POST http://extraction.ai.internal/v1/convert/file `
  -F "files=@dokument.pdf;type=application/pdf" `
  -F "to_formats=md" | ConvertFrom-Json
$antwort.document.md_content | Out-File -Encoding utf8 dokument.md
```

`curl.exe` muss mit Endung geschrieben werden — `curl` allein ist in PowerShell ein anderer Befehl.

Alle Endpunkte und Optionen: `http://extraction.ai.internal/docs`

### 5.2 Portainer

Oberfläche zur Verwaltung aller Container: Status, Logs, Konsole, Neustart, Ressourcenverbrauch. Ersetzt die PowerShell-Befehle aus Abschnitt 3.

**Schritt 1 — Dienst in `docker-compose.yml` einkommentieren**

In [`docker-compose.yml`](docker-compose.yml) die Kommentarzeichen an drei Stellen entfernen:

| Stelle | Was |
|---|---|
| Block `management:` unter `services:` | Der Dienst selbst |
| Eintrag `management:` unter `volumes:` | Sein Speicher |
| Liste `depends_on` beim Dienst `proxy` | `management` ergänzen |

Ohne den Schalter `--http-enabled` dient Portainer nur HTTPS auf Port 9443 aus.

**Schritt 2 — Block im `Caddyfile` einkommentieren**

In [`Caddyfile`](Caddyfile) die Kommentarzeichen vor dem Block `http://management.ai.internal` entfernen.

**Schritt 3 — Namen in die hosts-Datei eintragen**

Editor als Administrator starten, `C:\Windows\System32\drivers\etc\hosts` öffnen, an die vorhandene Zeile `management.ai.internal` anhängen, speichern.

```powershell
ipconfig /flushdns
```

**Schritt 4 — Starten und Setup-Token abholen**

```powershell
cd C:\Project\Local-LLM
docker compose up -d
docker logs management
```

In der Ausgabe die Zeile mit `setup_token=` suchen und den Wert kopieren.

**Schritt 5 — Konto anlegen**

1. Browser: `http://management.ai.internal`
2. **Setup token** einfügen, Benutzername und Passwort vergeben — mindestens zwölf Zeichen — **Create user**
3. Beim Bildschirm zu Edge Compute **Skip** wählen
4. **Get Started** klicken

Ab dem Start des Containers bleiben fünf Minuten, um Schritt 5 abzuschließen; danach beendet sich der Dienst im Container. `docker restart management` startet das Zeitfenster neu, mit neuem Token.

Der Mount von `/var/run/docker.sock` gibt Portainer volle Kontrolle über die Docker-Engine und damit über den Rechner — die Oberfläche nicht ins Netzwerk freigeben.

### 5.3 Open Terminal

Gibt dem Modell in `chat` eine Shell und ein Dateisystem: Befehle ausführen, Dateien anlegen und bearbeiten, Pakete installieren.

**Schritt 1 — Dienst in `docker-compose.yml` einkommentieren**

In [`docker-compose.yml`](docker-compose.yml) die Kommentarzeichen an drei Stellen entfernen:

| Stelle | Was |
|---|---|
| Block `shell:` unter `services:` | Der Dienst selbst |
| Eintrag `shell:` unter `volumes:` | Sein Speicher |
| Liste `depends_on` beim Dienst `proxy` | `shell` ergänzen |

Im Dienst-Block `OPEN_TERMINAL_API_KEY` auf einen selbst gewählten Schlüssel setzen.

Das Image `latest` bringt rund 4 GB Werkzeuge mit — Node.js, gcc, ffmpeg, LaTeX, Data-Science-Bibliotheken — und erlaubt Nachinstallieren zur Laufzeit. `ghcr.io/open-webui/open-terminal:slim` ist 430 MB groß, enthält nur git, curl und jq und kann nicht nachinstallieren.

**Schritt 2 — Block im `Caddyfile` einkommentieren**

In [`Caddyfile`](Caddyfile) die Kommentarzeichen vor dem Block `http://shell.ai.internal` entfernen.

**Schritt 3 — Namen in die hosts-Datei eintragen**

Editor als Administrator starten, `C:\Windows\System32\drivers\etc\hosts` öffnen, an die vorhandene Zeile `shell.ai.internal` anhängen, speichern.

```powershell
ipconfig /flushdns
```

**Schritt 4 — Starten und prüfen**

```powershell
cd C:\Project\Local-LLM
docker compose up -d
docker exec chat curl -s -o /dev/null -w "%{http_code}" http://shell:8000/docs
```

Die Ausgabe muss lauten:

```
200
```

**Schritt 5 — In `chat` anbinden**

1. Browser: `http://chat.ai.internal/admin`
2. **Settings** → **Integrations** → Abschnitt **Open Terminal** → **+**
3. Werte setzen:

   | Feld | Wert |
   |---|---|
   | URL | `http://shell:8000` |
   | API Key | der in Schritt 1 gesetzte Schlüssel |
   | Auth Type | `Bearer` |

4. **Save** klicken, dann die Seite neu laden.

Ohne das Neuladen erscheint das Terminal nicht in der Auswahl im Chat.

**Schritt 6 — Modell auf natives Function Calling umstellen**

1. Browser: `http://chat.ai.internal/admin`
2. **Settings** → **Models** → `qwen3.5:9b-q4_K_M` → **Advanced Params**
3. **Function Calling** auf `Native` setzen, **Save**.

Auf `Default` belassen ruft das Modell das Terminal nie auf.

**Schritt 7 — Test im Chat**

Neues Gespräch öffnen, das Terminal in der Auswahl aktivieren, senden:

```
Lege eine Datei test.txt mit dem Inhalt "hallo" an und zeige mir anschließend den Inhalt.
```

Die Werkzeugausgabe des Modells muss `hallo` enthalten.

Die Dokumentation nennt als Voraussetzung ein leistungsfähiges Modell und führt kleinere Modelle als Ausfallgrund an. Scheitert der Test, liegt es am Modell, nicht am Aufbau.

Die Shell läuft im Container und sieht nur dessen Dateisystem. Ein Mount des Docker-Sockets würde dem Modell volle Kontrolle über den Rechner geben — er ist hier bewusst nicht gesetzt.

### 5.4 InvokeAI

Erzeugt und bearbeitet Bilder. Eigenständige Oberfläche mit Leinwand, Masken und Modellverwaltung.

**Schritt 1 — Zugangstoken für Hugging Face besorgen**

Die FLUX-Modelle setzen eine Zustimmung zur Lizenz voraus.

1. Konto auf `https://huggingface.co` anlegen.
2. `https://huggingface.co/black-forest-labs/FLUX.2-klein-9B` aufrufen, Lizenz und Nutzungsbedingungen bestätigen.
3. Unter **Settings → Access Tokens** einen Token mit Leserecht erzeugen und kopieren.

**Schritt 2 — Dienst in `docker-compose.yml` einkommentieren**

In [`docker-compose.yml`](docker-compose.yml) die Kommentarzeichen an drei Stellen entfernen:

| Stelle | Was |
|---|---|
| Block `images:` unter `services:` | Der Dienst selbst |
| Eintrag `images:` unter `volumes:` | Sein Speicher |
| Liste `depends_on` beim Dienst `proxy` | `images` ergänzen |

Bei `HUGGING_FACE_HUB_TOKEN` den Token aus Schritt 1 eintragen.

**Schritt 3 — Block im `Caddyfile` einkommentieren**

In [`Caddyfile`](Caddyfile) die Kommentarzeichen vor dem Block `http://images.ai.internal` entfernen.

**Schritt 4 — Namen in die hosts-Datei eintragen**

Editor als Administrator starten, `C:\Windows\System32\drivers\etc\hosts` öffnen, an die vorhandene Zeile `images.ai.internal` anhängen, speichern.

```powershell
ipconfig /flushdns
```

**Schritt 5 — Starten**

```powershell
cd C:\Project\Local-LLM
docker compose up -d
```

Browser: `http://images.ai.internal`

**Schritt 6 — Modelle installieren**

Reiter **Model Manager** → Bereich **Add Model** → Feld für die HuggingFace-Repo-ID. Je Zeile eine Kennung eintragen und installieren:

| Repo-ID | Modell |
|---|---|
| `black-forest-labs/FLUX.2-klein-9B` | FLUX, Prompt-Treue |
| `black-forest-labs/FLUX.2-klein-9b-fp8` | Dasselbe Modell auf 8 Bit quantisiert, ab 12 GB Grafikspeicher |
| `Qwen/Qwen-Image` | Qwen, Text im Bild |

Der Download umfasst mehrere Gigabyte je Modell.

InvokeAI lädt Modelle nur teilweise in den Grafikspeicher und tauscht während der Erzeugung nach. Diese Einstellung ist ab Werk aktiv und macht Modelle nutzbar, die 16 GB überschreiten; die Erzeugung dauert dann länger. Das unquantisierte `FLUX.2-klein-9B` verlangt rund 29 GB und ist der Fall, für den es dieses Verhalten gibt; die fp8-Variante passt ohne Nachtauschen und zeigt, was das Nachtauschen kostet.

**Schritt 7 — Vergleich durchführen**

Für beide Modelle nacheinander mit identischem Prompt, Seed, Schrittzahl und Auflösung:

| Aufgabe | Prompt |
|---|---|
| Prompt-Treue | `drei Personen an einem Tisch, links ein Fenster, Tageslicht` |
| Text im Bild | `Ladenschild mit der Aufschrift "Bäckerei Mahler", Straßenansicht` |

Vor der Bilderzeugung den Grafikspeicher räumen:

```powershell
docker exec inference ollama stop qwen3.5:9b-q4_K_M
```

Das Sprachmodell lädt bei der nächsten Anfrage in `chat` selbst nach.

**Lizenz:** FLUX.2 klein 9B steht unter der FLUX Non-Commercial License. Erlaubt sind Test und Evaluierung, auch durch Unternehmen. Untersagt sind Produktivbetrieb und Umsatzerzielung. Die erzeugten Bilder dürfen frei verwendet werden. Qwen-Image steht unter Apache 2.0.

---

## 6. Rückbau Optional

### 6.1 Docling-API

Die erzeugten Markdown-Dateien löschen:

```powershell
Remove-Item *.md
```

Am Stack selbst ist nichts zurückzubauen: Die API gehört zum bereits vorhandenen Container `extraction`.

### 6.2 Portainer

```powershell
cd C:\Project\Local-LLM
docker compose stop management
docker compose rm -f management
docker volume rm local-llm_management
```

Danach in der `docker-compose.yml` den Dienst `management` und seinen Volume-Eintrag wieder auskommentieren, `management` aus dem `depends_on` des Dienstes `proxy` streichen, den Block im `Caddyfile` wieder auskommentieren und `management.ai.internal` aus der hosts-Datei entfernen.

```powershell
docker compose up -d
ipconfig /flushdns
```

### 6.3 Open Terminal

```powershell
cd C:\Project\Local-LLM
docker compose stop shell
docker compose rm -f shell
docker volume rm local-llm_shell
```

Danach in der `docker-compose.yml` den Dienst `shell` und seinen Volume-Eintrag wieder auskommentieren, `shell` aus dem `depends_on` des Dienstes `proxy` streichen, den Block im `Caddyfile` wieder auskommentieren und `shell.ai.internal` aus der hosts-Datei entfernen. In `chat` unter **Settings → Integrations → Open Terminal** den Eintrag löschen.

```powershell
docker compose up -d
ipconfig /flushdns
```

### 6.4 InvokeAI

```powershell
cd C:\Project\Local-LLM
docker compose stop images
docker compose rm -f images
docker volume rm local-llm_images
```

Danach in der `docker-compose.yml` den Dienst `images` und seinen Volume-Eintrag wieder auskommentieren, `images` aus dem `depends_on` des Dienstes `proxy` streichen, den Block im `Caddyfile` wieder auskommentieren und `images.ai.internal` aus der hosts-Datei entfernen.

```powershell
docker compose up -d
ipconfig /flushdns
```

---

## 7. Links

**Modelle**
- Qwen3.5 (Ollama): https://ollama.com/library/qwen3.5
- Qwen3-Embedding (Ollama): https://ollama.com/library/qwen3-embedding
- BGE-Reranker-v2-m3: https://huggingface.co/BAAI/bge-reranker-v2-m3

**Container**
- Ollama: https://ollama.com
- Open WebUI: https://docs.openwebui.com
- Docling-Serve: https://github.com/docling-project/docling-serve
- mcpo: https://github.com/open-webui/mcpo
- n8n: https://docs.n8n.io
- Caddy: https://caddyserver.com/docs/

**MCP-Server**
- Referenz-Server: https://github.com/modelcontextprotocol/servers
- Memory (inkl. `MEMORY_FILE_PATH`): https://www.npmjs.com/package/@modelcontextprotocol/server-memory
- Fetch: https://github.com/modelcontextprotocol/servers/tree/main/src/fetch
- Sequential Thinking: https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking
- Everything: https://github.com/modelcontextprotocol/servers/tree/main/src/everything

**Konfiguration**
- Open WebUI — RAG: https://docs.openwebui.com/features/chat-conversations/rag/
- Open WebUI — Docling: https://docs.openwebui.com/features/chat-conversations/rag/document-extraction/docling/
- Open WebUI — Tools: https://docs.openwebui.com/features/extensibility/plugin/tools/
- Open WebUI — Umgebungsvariablen: https://docs.openwebui.com/getting-started/env-configuration/
- Open WebUI — OpenAPI-Toolserver: https://docs.openwebui.com/openapi-servers/open-webui/
- Docker Compose — GPU-Support: https://docs.docker.com/compose/how-tos/gpu-support/
- Caddy — Caddyfile-Tutorial: https://caddyserver.com/docs/caddyfile-tutorial
- Caddy — Direktive `reverse_proxy`: https://caddyserver.com/docs/caddyfile/directives/reverse_proxy
- Caddy — Docker-Image: https://hub.docker.com/_/caddy
- n8n — Ollama-Credential: https://docs.n8n.io/integrations/builtin/credentials/ollama/
- n8n — Ollama Model Node, bekannte Probleme: https://docs.n8n.io/integrations/builtin/cluster-nodes/sub-nodes/n8n-nodes-langchain.lmollama/common-issues/
- n8n — Chat Trigger: https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-langchain.chattrigger/
- n8n — Basic LLM Chain: https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.chainllm

**Infrastruktur**
- NVIDIA CUDA on WSL: https://docs.nvidia.com/cuda/wsl-user-guide/index.html
- Docker Desktop GPU-Support: https://docs.docker.com/desktop/features/gpu/
- Docker Desktop WSL: https://docs.docker.com/desktop/features/wsl/
- Docker Desktop Windows — Installation: https://docs.docker.com/desktop/setup/install/windows-install/
- Docker Desktop — Einstellungen: https://docs.docker.com/desktop/settings-and-maintenance/settings/
- WSL — Befehle und Optionen: https://learn.microsoft.com/en-us/windows/wsl/basic-commands
- Docker Compose — Netzwerke und Namensauflösung: https://docs.docker.com/compose/how-tos/networking/

**Docling**
- Docling: https://docling-project.github.io/docling/
- Docling-Serve — API-Nutzung: https://github.com/docling-project/docling-serve/blob/main/docs/usage.md

**Portainer**
- Installation unter WSL / Docker Desktop: https://docs.portainer.io/start/install-ce/server/docker/wsl
- Ersteinrichtung: https://docs.portainer.io/start/install-ce/server/setup
- Setup-Token finden, überspringen, anpassen: https://docs.portainer.io/faqs/installing/setup-token
- CLI-Schalter: https://docs.portainer.io/advanced/cli
- Fünf-Minuten-Zeitfenster: https://docs.portainer.io/faqs/installing/your-portainer-instance-has-timed-out-for-security-purposes-error-fix

**Open Terminal**
- Überblick: https://docs.openwebui.com/features/open-terminal/
- Installation: https://docs.openwebui.com/features/open-terminal/setup/installation/
- Mit Open WebUI verbinden: https://docs.openwebui.com/features/open-terminal/setup/connecting/
- Dateibrowser: https://docs.openwebui.com/features/open-terminal/file-browser/
- Quelltext und Image-Varianten: https://github.com/open-webui/open-terminal

**InvokeAI**
- Dokumentation: https://invoke.ai/
- Docker: https://invoke.ai/configuration/docker/
- Hardwareanforderungen: https://invoke.ai/start-here/system-requirements/
- Low-VRAM-Modus: https://invoke.ai/configuration/low-vram-mode/
- Modelle installieren: https://invoke.ai/concepts/models/

**Bildmodelle**
- FLUX.2 klein — Modellübersicht: https://bfl.ai/blog/flux2-klein-towards-interactive-visual-intelligence
- FLUX.2 klein 9B — Lizenztext: https://huggingface.co/black-forest-labs/FLUX.2-klein-9B/blob/main/LICENSE.md
- Qwen-Image — Modellkarte: https://huggingface.co/Qwen/Qwen-Image

