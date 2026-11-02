# EDITH Backend

Cross-platform Python/FastAPI backend for EDITH, an ESP32-S3 desktop companion. Provides browser chat, contextual OLED face selection through LM Studio, and local or authenticated polling control of the device.

Works with Python 3.11+ on Windows and Linux. CachyOS/KDE uses the Linux instructions below. The application uses portable paths and SQLite; no CUDA or GPU packages are required for the backend itself. Local model speed depends on the machine running LM Studio.

## 1. Install prerequisites

Install Git, uv and optionally VS Code. If uv is already installed, skip its installer.

### Windows 11 — PowerShell

Install Git for Windows from https://git-scm.com/downloads/win, then install uv:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Reopen your terminal and check:

```powershell
git --version
uv --version
```

### CachyOS / Arch Linux — terminal

Install the basic tools using your system package manager:

```bash
sudo pacman -Syu --needed git curl
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Reopen your terminal so uv is on PATH, then check:

```bash
git --version
uv --version
```

uv installs the Python version specified by `.python-version` if needed. Do not install project dependencies into CachyOS's system Python.

## 2. Clone and install

### Windows — PowerShell

Choose a parent directory for your projects. These commands reproduce the author's folder layout on a new machine:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\Documents\Uni\EDITH" | Out-Null
Set-Location "$env:USERPROFILE\Documents\Uni\EDITH"
git clone https://github.com/QZainSami/edith-backend.git "EDITH Backend"
Set-Location "EDITH Backend"
uv sync --locked
Copy-Item .env.example .env
```

### Linux / CachyOS — bash or zsh

```bash
mkdir -p ~/Documents/Uni/EDITH
cd ~/Documents/Uni/EDITH
git clone https://github.com/QZainSami/edith-backend.git "EDITH Backend"
cd "EDITH Backend"
uv sync --locked
cp .env.example .env
```

Copy the example only on the first setup; do not overwrite an existing `.env`. `uv.lock` is committed and supports resolving dependencies for each platform. Each machine gets its own `.venv`; never copy the Windows environment to Linux. No activation is needed.

## 3. Configure LM Studio and EDITH

Install LM Studio from https://lmstudio.ai/download on the machine that will run the model. Load Gemma, then start its local server. Linux downloads include an AppImage; make the downloaded file executable using KDE Dolphin's Properties → Permissions, or `chmod +x /path/to/downloaded.AppImage`, then launch it. Check LM Studio's current system requirements; CachyOS is not a specifically certified distribution. If the laptop cannot run the model comfortably, use rules mode or connect securely to the home PC instead.

Find the exact API model identifier:

**Windows PowerShell:**

```powershell
(Invoke-RestMethod http://127.0.0.1:1234/v1/models).data | Select-Object id
```

**Linux:**

```bash
curl -fsS http://127.0.0.1:1234/v1/models
```

If LM Studio authentication is enabled, use its token for this request and set `LMSTUDIO_API_KEY` in `.env`. Do not share or commit the token.

Edit `.env` in VS Code (or any text editor):

```dotenv
DEVICE_TRANSPORT=local
EDITH_IP=192.168.1.123
DEVICE_TIMEOUT=3
LMSTUDIO_MODE=auto
LMSTUDIO_URL=http://127.0.0.1:1234
LMSTUDIO_MODEL=google/gemma-4-e2b
LMSTUDIO_TIMEOUT=90
LMSTUDIO_API_KEY=
```

Replace the IP and model ID with your actual values. `LMSTUDIO_URL` is the server origin without `/v1`. The example ID is not guaranteed to match every download. `127.0.0.1` always means the machine running the backend: on the laptop it does not refer to the Windows PC. For a remote home model, use an authenticated secure connection; a localhost-only SSH forward can retain this URL once SSH access to the home PC has been configured. No remote tunnel is installed by this project.

To develop without any model, set `LMSTUDIO_MODE=off`. Chat then uses labeled fixed replies. Leave `EDITH_IP` blank to develop without hardware. Restart after changes to `.env`; process environment variables override that file.

## 4. Run — same command on Windows and Linux

From the repository root:

```text
uv run python -m uvicorn app:app --host 127.0.0.1 --port 8000 --workers 1
```

Open http://127.0.0.1:8000. Keep the terminal open; Ctrl+C stops the server. `Reply: lmstudio` identifies generated replies; `Reply: rules` identifies fallback replies. The UI also shows which detector selected the face.

For VS Code, open the repository folder and select its interpreter:

- Windows: `.venv\Scripts\python.exe`
- Linux: `.venv/bin/python`

All commands above work from the integrated terminal. Quote paths containing spaces. Do not copy `.venv`, `data`, cached files, or `.vscode` settings between operating systems.

## 5. ESP32 polling mode — same on both operating systems

Use this when the ESP32 initiates the device connection. Set these additional values in the private `.env`:

```dotenv
DEVICE_TRANSPORT=poll
EDITH_DEVICE_TOKEN=REPLACE_WITH_A_RANDOM_TOKEN_OF_AT_LEAST_32_CHARACTERS
EDITH_WEB_USER=edith
EDITH_WEB_PASSWORD=REPLACE_WITH_A_RANDOM_PASSWORD_OF_AT_LEAST_16_CHARACTERS
```

Generate a fresh secret with the following command; run it twice for separate device and web secrets:

```text
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Replace the placeholders; do not use the example strings as passwords. Match the device token in the middleware's private `include/edith_config.h`. The browser password belongs only in the backend. Keep an existing working token if reusing the same ESP32; changing the token on only one side breaks polling.

Run the backend on the trusted LAN:

```text
uv run python -m uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1
```

Find the backend machine's LAN IPv4 address using `ipconfig` on Windows, or `ip -4 address` and `ip route` on Linux. Set the middleware's server URL to `http://THAT-IP:8000` for this temporary LAN test. The server address must be updated when moving the backend from PC to laptop or changing networks. Do not use `0.0.0.0` as the device's destination address.

Allow inbound TCP port 8000 only on the trusted LAN using the host firewall if needed; do not disable the firewall. Both machines/devices must be on a reachable network. For public hosting use HTTPS and the correct root CA, with HTTP test mode disabled in firmware. The local polling test has passed on the author's Windows/ESP32 setup. Public hosting and hotspot end-to-end testing remain pending.

Open the browser page and enter `EDITH_WEB_USER` and `EDITH_WEB_PASSWORD`. Click a mood, wait a few seconds and refresh status. `queued` means requested; `applied: true` means acknowledged after the device's transition completed. See [HOSTING.md](HOSTING.md) for the protocol and deployment details and [LOCAL_POLL_TEST.md](LOCAL_POLL_TEST.md) for the test checklist.

## Tests — Windows and Linux

```text
uv sync --locked
uv run python -m pytest -q
```

Tests simulate model and device responses and isolate themselves from the private `.env`; they need no live model or OLED. Linux execution has not yet been verified on the author's laptop. Windows tests and the real local polling flow have been verified.

## How replies and faces work

Gemma returns a structured reply, mood and short reason using recent conversation. The backend validates the face against eight supported moods. If generation fails, transparent keyword/context rules provide a fixed reply and face with a warning. This is a face suggestion, not an emotion diagnosis. `emotion.py` contains the prompt, fallback rules and response validation.

The browser keeps six completed exchanges in memory; Clear chat or page refresh discards them. The backend writes only device mailbox state to SQLite (`data/device.sqlite3` by default); chat messages are not stored there. Set `EDITH_STATE_DB` to another writable path if needed. Use one backend instance/worker; tabs share the physical device. Model responses are limited to 500 generated tokens per request.

## API

Interactive schemas: http://127.0.0.1:8000/docs

- `GET /api/status`: firmware/mailbox state and model configuration.
- `GET /api/lmstudio`: available API model IDs.
- `POST /api/mood`: JSON `{"name":"happy"}`.
- `POST /api/chat`: JSON `{"message":"Hello","history":[]}`.
- `POST /api/device/poll`: authenticated firmware polling.
- `GET /healthz`: minimal public health check.

Poll mode requires separate device and browser credentials. Local mode has optional browser authentication. Network/model errors use explicit warnings and fallback replies; invalid inputs return HTTP 422.

## Working between PC and laptop

On each machine, clone once and keep private configuration locally. Pull committed changes before working:

```text
git pull --ff-only
uv sync --locked
```

Commit and push your source changes before switching machines. If local edits block a pull, commit or deliberately stash them first; do not force-reset them. `.env`, generated environments, private backups and runtime state are excluded from Git. Transfer needed secrets separately through a trusted private channel, never by committing them.

## Hosting, roadmap and license

Deployment preparation: [HOSTING.md](HOSTING.md). Planned touch, wake-word, voice and speaking-mouth features: [ROADMAP.md](ROADMAP.md). Your home PC must remain awake and online if it serves the model for a hosted backend. Free hosting does not make localhost on your PC reachable from the cloud.

Firmware: [QZainSami/edith-middleware](https://github.com/QZainSami/edith-middleware).

[MIT](LICENSE), copyright 2026 QZainSami. Dependencies and downloaded models retain their own licenses.

## References

- [uv installation](https://docs.astral.sh/uv/getting-started/installation/)
- [LM Studio requirements](https://lmstudio.ai/docs/app/system-requirements)
- [LM Studio API](https://lmstudio.ai/docs/developer/openai-compat)
