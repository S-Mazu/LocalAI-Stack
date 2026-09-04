# Project Plan

Open work and ideas. Reference the stack each item belongs to.

## LocalAI-Stack

**Capabilities**
- **ComfyUI** — image generation, callable by the model through a tool or from `automation`. https://docs.comfy.org/
- **SearXNG** — self-hosted meta search as a search provider for `chat`, without API keys and without requests to third parties. https://docs.searxng.org/

**Access**
- **oauth2-proxy** — sign-in through an existing identity provider instead of local accounts. Requires HTTPS: Entra and Google allow `http://` redirect URIs only for `localhost`. https://oauth2-proxy.github.io/oauth2-proxy/ · Open WebUI SSO: https://docs.openwebui.com/features/sso/

**Operations**
- **Langfuse** — records which text chunks were retrieved and which tools were called. https://langfuse.com/self-hosting
