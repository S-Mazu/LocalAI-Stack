# Project Plan

Open work and ideas. Reference the stack each item belongs to.

## LocalAI-Stack

**Capabilities**
- **ComfyUI** — node-based alternative to InvokeAI, callable by the model through a tool or from `automation`. https://docs.comfy.org/
- **SearXNG** — self-hosted meta search as a search provider for `chat`, without API keys and without requests to third parties. https://docs.searxng.org/
- **Coding Agent + Harness** — command-line tool that reads and edits source code and runs commands; reaches Ollama over the OpenAI-compatible endpoint.

**Access**
- **oauth2-proxy** — sign-in through an existing identity provider instead of local accounts. Requires HTTPS: Entra and Google allow `http://` redirect URIs only for `localhost`. https://oauth2-proxy.github.io/oauth2-proxy/ · Open WebUI SSO: https://docs.openwebui.com/features/sso/

**Operations**
- **Langfuse** — records which text chunks were retrieved and which tools were called. https://langfuse.com/self-hosting
- **oikb** — command-line tool that syncs a knowledge collection in `chat` incrementally against a source. https://docs.openwebui.com/ecosystem/knowledge-base-sync/

## Conventions

- **Shared-list rule in `CLAUDE.md`** — the maintainer doubts it is usable. Deeper dive the next time a shared list comes up. Recorded 2026-09-10.
