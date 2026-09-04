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
| `extraction` | `http://extraction.ai.internal` | `http://localhost:5001` |
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
| Zweite `depends_on`-Zeile beim Dienst `proxy` | Die Variante mit `management`; die erste dafür auskommentieren |

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

Danach in der `docker-compose.yml` den Dienst `management`, seinen Volume-Eintrag und die `depends_on`-Variante mit `management` wieder auskommentieren, den Block im `Caddyfile` wieder auskommentieren und `management.ai.internal` aus der hosts-Datei entfernen.

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
