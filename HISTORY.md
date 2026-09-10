# History

## 2026-08-28 — LocalAI-Stack built
Stack: LocalAI-Stack
Ollama, Open WebUI, Docling, mcpo, n8n and Caddy set up as a fully local RAG/tools chat stack on Windows/WSL2/Docker.

## 2026-08-31 — Repo reorganized into sub-projects
Stack: LocalAI-Stack, MTP-MultiTokenPrediction
Root-level stack files moved into `LocalAI-Stack/`. `MTP-MultiTokenPrediction/` added as a second sub-project. Root `README.md` introduced as a project chooser. `HISTORY.md`, `FILEMAP.md`, `PROJECTPLAN.md` created; bilingual README convention adopted, with English versions written for both existing sub-project READMEs.

## 2026-08-31 — Config files extracted, sub-project READMEs trimmed
Stack: MTP-MultiTokenPrediction, LocalAI-Stack
`docker-compose.yml` and `bench_iso.py` extracted from the MTP-MultiTokenPrediction README into
standalone files (LocalAI-Stack already had its three config files as standalone files). All
four sub-project READMEs (EN + DE) now reference these files by path instead of embedding their
full content.

## 2026-09-04 — News.md synced into LocalAI-Stack
Stack: LocalAI-Stack, MTP-MultiTokenPrediction
Proxy hostnames changed from bare container names to `*.ai.internal`. `chat` gained two
sysctls: WSL2's narrow ephemeral port range plus two-minute TIME_WAIT exhausted the ports
its outbound calls need. Docling API and Portainer promoted from idea to documented
optional sections, with the Portainer service and proxy block shipping commented out in
`docker-compose.yml` and `Caddyfile` so enabling them is uncommenting. Open WebUI tool
binding moved to Settings → Integrations → External Tool Servers. All code comments
translated to English; German is now README-DE only. `install.cmd` removed as a relic.
News.md removed; its content now lives in the sub-project files it described.

## 2026-09-10 — Open Terminal and InvokeAI added as optional components
Stack: LocalAI-Stack
`shell` (Open Terminal) and `images` (InvokeAI) added to `docker-compose.yml` and `Caddyfile`,
shipped commented out like Portainer. The `depends_on` of `proxy` no longer carries one commented
variant per optional service — with three of them the variants outnumber the services, so the list
is extended by hand instead; Portainer's section was rewritten to match. Open Terminal is checked
against `/docs`, not the undocumented `/health`, and needs the model's Function Calling on
`Native`; left on `Default` it is never called. InvokeAI documents the unquantised
`FLUX.2-klein-9B` next to its fp8 build, to measure what partial model loading costs on 16 GB.

## 2026-09-10 — Live stack checked against the HowTo
Stack: LocalAI-Stack
Docker-side check of the running stack against README sections 2, 3 and 5. Containers, images,
ports, hosts entries, models, GPU passthrough, MCP tool paths and volume names all match. The
deployed config files in `C:\Project\Local-LLM` were an older revision without the optional
commented blocks, which left sections 5.2 to 5.4 with nothing to uncomment; they were replaced
with the repo copies and `proxy` restarted. The `extraction` row of section 3.14 pointed at the
container root, which has no route — it now points at `/ui`, where section 5.1 already sent the
reader.

## 2026-09-10 — InvokeAI enabled on the live stack, proxy restart added to the optional sections
Stack: LocalAI-Stack
`images` enabled in the deployed stack and reached under `images.ai.internal`, GPU passed through.
Enabling it exposed a gap in all three optional sections: `docker compose up -d` does not recreate
`proxy` when only the bind-mounted `Caddyfile` changed, so the new hostname stayed unrouted until
`proxy` was restarted by hand. Sections 5.2 to 5.4 and their teardown counterparts 6.2 to 6.4 now
carry `docker compose restart proxy`.

## 2026-09-10 — InvokeAI model install corrected against the running stack
Stack: LocalAI-Stack
Installing models exposed three defects in section 5.4. InvokeAI's SSRF guard refuses the Hugging
Face CDN, which resolves over NAT64 under WSL2, so every install failed until
`allow_private_download_urls` was set — now its own step. The fp8 build is a single file, not a
Diffusers folder, so the repo ID in step 7 gave `409: No downloadable files found` and is replaced
by the file URL. The `HUGGING_FACE_HUB_TOKEN` line now ships commented out: an invalid token makes
Hugging Face reject public repositories too.
