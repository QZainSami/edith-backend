# EDITH Backend

This version replaces Ollama with LM Studio. Keep the working ESP32 firmware: the backend still uses GET /status and GET /mood?name=normal|happy|sad|angry|sleepy|curious|thinking|uwu. No extra hardware or firmware changes are required.

## Start LM Studio

1. Open LM Studio and load your downloaded Gemma 4 E2B model.
2. Open its Developer tab and start the local server. This project defaults to http://127.0.0.1:1234; use the port shown by your installation.
3. Find the exact model identifier using this PowerShell command:

```powershell
(Invoke-RestMethod http://127.0.0.1:1234/v1/models).data | Select-Object id
```

Copy the ID for Gemma, not an embedding model. The displayed download name and API ID may differ. If your LM Studio server requires authentication, provide its token as LMSTUDIO_API_KEY in .env. Keep tokens out of browser code.

## Start EDITH

Extract the project into a fresh folder, then open that folder in VS Code. In its PowerShell terminal:

```powershell
uv sync
Copy-Item .env.example .env
```

If updating an existing folder, keep your existing .env and edit it instead of copying over it. Keep EDITH_IP, remove the old OLLAMA settings, and add:

```dotenv
EDITH_IP=192.168.1.123
DEVICE_TIMEOUT=3
LMSTUDIO_MODE=auto
LMSTUDIO_URL=http://127.0.0.1:1234
LMSTUDIO_MODEL=PASTE_THE_EXACT_MODEL_ID_HERE
LMSTUDIO_TIMEOUT=90
LMSTUDIO_API_KEY=
```

Replace the ESP32 IP and model placeholder with your actual values. LMSTUDIO_URL is the server origin without /v1. Leave EDITH_IP blank to try chat without the OLED. Restart EDITH after changing .env. Process environment variables override .env values.

```powershell
uv run python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. Click Check LM Studio to check the model list, then send a message. **Reply: lmstudio** means the model generated it. **Reply: rules** means a fixed reply; read the warning if LM Studio was expected. LMSTUDIO_MODE=off deliberately uses only fixed replies.

uv manages Python 3.11 and .venv; no activation or pip commands are needed. The first uv sync generates uv.lock; no lockfile is bundled. Select .venv\Scripts\python.exe in VS Code if using its Python extension. requirements files remain for compatibility.

## What runs where

Browser → Python backend → LM Studio for replies, and Python backend → ESP32 HTTP endpoints for faces. In model mode the device gets thinking during generation, then the guessed mood. HTTP success is a firmware acknowledgement, not independent verification of the screen. Existing firmware handles animation.

Emotion detection stays transparent and rule based. Whole-word/phrase priority: sad, angry, sleepy, uwu, happy, thinking, curious. A negator within the previous three words suppresses a match. An unmatched question mark gives curious; otherwise normal. RULES and REPLIES in app.py are editable. These heuristics do not reliably understand sarcasm, complex negation, other languages, or mixed emotions. There is no trained emotion classifier or confidence probability.

The browser retains six completed exchanges in memory and supplies them as model context. Refresh or Clear chat discards them. No chat database is written. The model cannot operate the relay or buzzer, see, or hear. Physical device actions are serialized; run one worker. Multiple tabs share the OLED.

Device failure does not stop chat. Model timeout, missing model ID, invalid responses, or a stopped LM Studio server cause a fixed reply with a warning. No model download or automatic network retry occurs. The timeout is configurable up to 300 seconds. Chat replies are limited to 300 generated tokens per call.

## API and checks

Interactive API docs: http://127.0.0.1:8000/docs

- GET /api/status: firmware status and selected model configuration.
- GET /api/lmstudio: available model IDs.
- POST /api/mood: JSON {"name":"happy"}.
- POST /api/chat: JSON {"message":"Hello","history":[]}.

Chat returns reply, source, emotion, device, thinking_device, and warning. Invalid input returns HTTP 422. Device failures have device.ok=false.

```powershell
uv run python -m pytest -q
```

Tests use simulated responses and require no hardware or live model. Verify your real setup by opening http://YOUR-ESP32-IP/status, testing mood buttons, and confirming Reply: lmstudio on a chat. If connection fails, check service ports, ESP32 IP, same LAN, VPN routing, and model loading. A model HTTP 400/404 can indicate the wrong ID or unsupported request; check LM Studio's server logs. The backend sends non-streaming OpenAI-compatible chat completions directly with HTTPX; no OpenAI account or cloud API key is used.

## Future hosting

Current setup runs on your PC. Hosting only the web page will not make local LM Studio or an ESP32 private LAN address reachable from a cloud backend. For an anywhere-accessible version, we will need authentication, HTTPS, a reachable model service, and a device connection initiated outward (for example authenticated MQTT over TLS or a persistent secure connection). Do not forward the ESP32 or LM Studio ports directly to the public internet. This local prototype has no user authentication and is not ready for public deployment.

A local model on your PC requires that PC to stay on. Independent hosted use requires a hosted model service or GPU server. We can decide the final deployment after the local conversation works.

## Extra components

The photos show a single-channel relay module, female jumper leads, and a two-pin buzzer. The photo cannot confirm the buzzer type/rating or relay input compatibility with 3.3 V. Keep them disconnected for this step. Later, the buzzer can provide short status sounds after checking its specification and driver needs. A buzzer does not provide spoken voice. For a relay demo, use only a suitable low-voltage load; do not connect household mains.

## References

- LM Studio server and API: https://lmstudio.ai/docs/developer
- Chat completions and models endpoints: https://lmstudio.ai/docs/developer/openai-compat
- uv workflow: https://docs.astral.sh/uv/guides/projects/

Milestone 5 connection work is documented in HOSTING.md. The future voice/touch features are tracked in ROADMAP.md. Local mode remains the default.


## Related project

ESP32 firmware: [QZainSami/edith-middleware](https://github.com/QZainSami/edith-middleware).

## License

[MIT](LICENSE), copyright 2026 QZainSami. Dependencies and downloaded models retain their own licenses.
