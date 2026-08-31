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
