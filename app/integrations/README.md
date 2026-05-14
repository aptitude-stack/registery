# app.integrations module

External provider adapters used by application wiring.

## Current State

- `openai_embeddings.py`: OpenAI embeddings adapter implementing the core
  embedding provider port.

Keep SDK-specific code here so core services depend on ports and pure helpers
rather than provider clients.
