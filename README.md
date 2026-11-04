# 🤖 EDITH Backend

Cross-platform Python/FastAPI backend for EDITH, an ESP32-S3 desktop companion. Provides browser chat, contextual OLED face selection through LM Studio, and local or authenticated polling control of the device.

Works with Python 3.11+ on Windows and Linux. CachyOS/KDE uses the Linux instructions below. The application uses portable paths and SQLite; no CUDA or GPU packages are required for the backend itself. Local model speed depends on the machine running LM Studio.

## 🚀 Quick start

**You need:** [Git](https://git-scm.com/downloads), [uv](https://docs.astral.sh/uv/getting-started/installation/) and, for AI replies, [LM Studio](https://lmstudio.ai/download). VS Code is optional. Already installed? Start here.

### 1. Clone the project — Windows or Linux

Run these commands wherever you want to keep the project:

```bash
git clone https://github.com/QZainSami/edith-backend.git
cd edith-backend
uv sync --locked
```

### 2. Create your settings file

**Windows PowerShell:**

```powershell
Copy-Item .env.example .env
```

**Linux / CachyOS:**

```bash
cp .env.example .env
```

Do this once. Keep your existing `.env` when updating. uv creates the Python environment automatically; no activation or pip commands are needed.

### 3. Connect LM Studio

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

### 4. Start EDITH — Windows or Linux

From the repository root:

```text
uv run python -m uvicorn app:app --host 127.0.0.1 --port 8000 --workers 1
```

Open http://127.0.0.1:8000. Keep the terminal open; Ctrl+C stops the server. `Reply: lmstudio` identifies generated replies; `Reply: rules` identifies fallback replies. The UI also shows which detector selected the face.

💡 In VS Code, open the cloned folder and select its Python interpreter:

- Windows: `.venv\Scripts\python.exe`
- Linux: `.venv/bin/python`

Run commands from the project folder. Each computer needs its own `.venv`; do not copy virtual environments or build caches between Windows and Linux.

## 📡 Connect the ESP32

Choose the connection method that matches your firmware:

| Mode | What happens | Settings |
| --- | --- | --- |
| `local` | Backend sends commands directly to the ESP32's LAN IP | `DEVICE_TRANSPORT=local`, `EDITH_IP=your-device-IP` |
| `poll` | ESP32 asks the backend for commands | `DEVICE_TRANSPORT=poll`, matching device token |

The quick-start example above uses local mode. For polling mode, set these additional values in the private `.env`:

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

Allow inbound TCP port 8000 only on the trusted LAN using the host firewall if needed; do not disable the firewall. Both machines/devices must be on a reachable network. For public hosting use HTTPS and the correct root CA, with HTTP test mode disabled in firmware. Local polling has been verified on Windows with the ESP32. Public hosting and hotspot end-to-end testing remain pending.

Open the browser page and enter `EDITH_WEB_USER` and `EDITH_WEB_PASSWORD`. Click a mood, wait a few seconds and refresh status. `queued` means requested; `applied: true` means acknowledged after the device's transition completed. See [HOSTING.md](HOSTING.md) for the protocol and deployment details and [LOCAL_POLL_TEST.md](LOCAL_POLL_TEST.md) for the test checklist.

## 🧪 Run tests

```text
uv sync --locked
uv run python -m pytest -q
```

Tests simulate model and device responses and isolate themselves from the private `.env`; they need no live model or OLED. Windows tests and the real local polling flow have been verified. Linux hardware testing is still pending.

## 🧠 How it works

Gemma returns a structured reply, mood and short reason using recent conversation. The backend validates the face against eight supported moods. If generation fails, transparent keyword/context rules provide a fixed reply and face with a warning. This is a face suggestion, not an emotion diagnosis. `emotion.py` contains the prompt, fallback rules and response validation.

The browser keeps six completed exchanges in memory; Clear chat or page refresh discards them. The backend writes device and companion state to SQLite (`data/device.sqlite3` by default); chat messages are not stored there. Set `EDITH_STATE_DB` to another writable path if needed. Use one backend instance/worker; tabs share the physical device. Model responses are limited to 500 generated tokens per request.

## 🔌 API

Interactive schemas: http://127.0.0.1:8000/docs

- `GET /api/status`: firmware/mailbox state and model configuration.
- `GET /api/lmstudio`: available API model IDs.
- `POST /api/mood`: JSON `{"name":"happy"}`.
- `POST /api/chat`: JSON `{"message":"Hello","history":[]}`.
- `POST /api/device/poll`: authenticated firmware polling.
- `GET /healthz`: minimal public health check.

Poll mode requires separate device and browser credentials. Local mode has optional browser authentication. Network/model errors use explicit warnings and fallback replies; invalid inputs return HTTP 422.

## 💻 Work on another computer

On each machine, clone once and keep private configuration locally. Pull committed changes before working:

```text
git pull --ff-only
uv sync --locked
```

Commit and push your source changes before switching machines. If local edits block a pull, commit or deliberately stash them first; do not force-reset them. `.env`, generated environments, private backups and runtime state are excluded from Git. Transfer needed secrets separately through a trusted private channel, never by committing them.

## 🗺️ Hosting and future features

Deployment preparation: [HOSTING.md](HOSTING.md). Planned touch, wake-word and audio-synchronized speaking features: [ROADMAP.md](ROADMAP.md). Your home PC must remain awake and online if it serves the model for a hosted backend. Free hosting does not make localhost on your PC reachable from the cloud.

Firmware: [QZainSami/edith-middleware](https://github.com/QZainSami/edith-middleware).

## 📄 License

[MIT](LICENSE), copyright 2026 QZainSami. Dependencies and downloaded models retain their own licenses.

## 🛠️ Need to install Git or uv?

<details>
<summary>Show Windows and CachyOS installation commands</summary>

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

uv installs the required Python version automatically. Keep project dependencies out of the system Python.

</details>

## 📚 Useful links

- [uv installation](https://docs.astral.sh/uv/getting-started/installation/)
- [LM Studio requirements](https://lmstudio.ai/docs/app/system-requirements)
- [LM Studio API](https://lmstudio.ai/docs/developer/openai-compat)

## 💤 Dashboard, timers and speaking animation

Update and upload the matching middleware firmware, restart this backend using the usual uv command, then refresh the browser. No new Python packages or changes to existing private credentials are required.

- **Sleep / dashboard** shows the date, clock, city, temperature, humidity and a weather icon. This is a connected display mode, not ESP32 deep sleep.
- Search for your city, choose the correct result, then **Save location & time zone**. The offset starts from your browser; Pakistan is `300` minutes. Save it again after a time-zone or daylight-saving change.
- Weather uses [Open-Meteo](https://open-meteo.com/) and refreshes about every 10 minutes. Failed requests retain the last reading; the OLED marks readings older than 30 minutes with `*`. Missing readings display placeholders. Internet access is required for weather.
- Start a timer from 1 second to 24 hours. It opens a dedicated OLED countdown with large digits, a progress bar and a slow orbiting dot, and continues on the ESP32 during a temporary network outage. **TIME UP** remains until **Cancel / dismiss**. There is no audible alarm yet. Backend state persists across restarts; a powered-off ESP32 needs a connection to restore its timer.
- Type `EDITH sleep`, `EDITH wake up`, `set a timer for 5 minutes`, or `cancel timer`. Only these explicit commands operate controls; ordinary conversation goes to the normal chat flow.
- Ordinary chat wakes the face. When a reply arrives, the mouth animates for an estimated reading duration (1.5–20 seconds). This simulates speaking; there is no generated audio or audio-synchronized lip movement yet.

The clock is synchronized from the backend and advances locally between updates. No battery percentage is shown because battery sensing hardware is not configured.

New API routes: `POST /api/screen`, `POST /api/timer`, `GET /api/locations`, `POST /api/dashboard`, and authenticated `POST /api/device/poll-v2`. Schemas are in `/docs`. The original face-only poll endpoint remains available for older firmware, but dashboard and mouth animation require version 2 firmware. In local mode the backend also sends `POST /companion` to the ESP32. SQLite now stores dashboard preferences, timer and transient speaking state alongside the device mailbox; it does not store chat text.

## ⚡ Boot animation, stopwatch and alarm

Update all three projects together: restart this backend, build/upload the middleware, then build/install the Android app. No credentials or new packages are needed.

- Startup now includes a short scan-line/glitch sequence on Android and the OLED.
- Stopwatch: start/resume, pause and reset via `POST /api/stopwatch` with `{"action":"start"}`, `"pause"` or `"reset"`. Elapsed time is persisted in SQLite, survives backend restarts and continues locally on a powered ESP32 through temporary network loss. Limit: 99:59:59.99. Starting, pausing or resetting selects the stopwatch display; face/dashboard controls can leave it while it runs in the background.
- Alarm: `POST /api/alarm` with `{"at":UNIX_SECONDS,"utc_offset":300}` schedules one future alarm within 7 days; `{"at":null}` cancels/dismisses it. Android and the web page choose the next occurrence of a selected clock time in their own local time zone. The alarm is one-time, not recurring. The OLED alert remains until dismissed.
- Display priority: due alarm, active/finished timer, selected stopwatch, dashboard/face. Dismissing an alarm reveals the underlying display.
- Alarms are **visual only**: there is no speaker alarm or Android background notification. The ESP32 must stay powered; after power loss it needs a backend connection to restore state. A missed alarm appears due on reconnection.

The v2 wire packet retains its original 16 fields and appends six optional fields: `TOOLS1`, stopwatch event ID, elapsed milliseconds, running flag, alarm event ID and remaining alarm milliseconds (`-1` means none). Firmware accepts legacy 16-field packets. Stopwatch mode requires the updated firmware; old firmware will not understand that mode. All packets remain below the existing 512-byte limit.

## 💬 Reply style
The system prompt in emotion.py asks for warm, direct replies, normally 1–2 short sentences (about 15–45 words). One relevant emoji is optional; emojis are avoided in serious distress and code/commands. Requests for detailed explanations may receive longer answers. This is a prompt preference, not a guaranteed word cap. Restart the backend after editing the prompt.
