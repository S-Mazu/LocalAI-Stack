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

**Open on the running stack**
- **Verify the four image models register in InvokeAI** — downloads were still running when the session ended. Check `Model Manager` lists FLUX.2-klein-9B, the fp8 build, its VAE and text encoder, and Qwen-Image.
- **Run the comparison in section 5.4** — same prompt, seed, step count and resolution across FLUX and Qwen, then FLUX Diffusers against fp8 to measure what partial model loading costs on 16 GB. Free the graphics memory first with `docker exec inference ollama stop qwen3.5:9b-q4_K_M`.
- **Check the in-app configuration against the HowTo** — sections 3.11, 3.12 and 3.13 were left out of the docker-side check. Needs API keys for `chat` and `automation`, or a read of their SQLite volumes.

## Conventions

- **Shared-list rule in `CLAUDE.md`** — the maintainer doubts it is usable. Deeper dive the next time a shared list comes up. Recorded 2026-09-10.
