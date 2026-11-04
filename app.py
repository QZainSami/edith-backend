"""EDITH Milestone 4: local typed chat and ESP32 mood control."""
import asyncio
from contextlib import asynccontextmanager
import os
import secrets
import base64
import contextlib
import re
import time
import uuid
from companion import Companion, parse_command
from weather_service import refresh_weather, weather_loop
from device_mailbox import Mailbox
from pathlib import Path
from emotion import detect, RESPONSE_FORMAT, SYSTEM_PROMPT, parse_model
from typing import Literal
from urllib.parse import urlsplit

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
Mood = Literal['normal', 'happy', 'sad', 'angry', 'sleepy', 'curious', 'thinking', 'uwu']
MOODS = ('normal', 'happy', 'sad', 'angry', 'sleepy', 'curious', 'thinking', 'uwu')


def base_url(value: str) -> str:
    value = value.strip().rstrip('/')
    if not value:
        return ''
    if '://' not in value:
        value = 'http://' + value
    parsed = urlsplit(value)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ('', '/')):
        raise ValueError('Use an IP/hostname or http(s) base URL without a path or credentials.')
    return value


DEVICE_URL = base_url(os.getenv('EDITH_IP', ''))
DEVICE_TRANSPORT = os.getenv('DEVICE_TRANSPORT', 'local').strip().lower()
DEVICE_TOKEN = os.getenv('EDITH_DEVICE_TOKEN', '')
WEB_USER = os.getenv('EDITH_WEB_USER', '')
WEB_PASSWORD = os.getenv('EDITH_WEB_PASSWORD', '')
if DEVICE_TRANSPORT not in ('local', 'poll'):
    raise ValueError('DEVICE_TRANSPORT must be local or poll')
if DEVICE_TRANSPORT == 'poll' and (len(DEVICE_TOKEN) < 32 or not WEB_USER or len(WEB_PASSWORD) < 16):
    raise ValueError('Poll mode requires a 32+ character device token, web user and 16+ character web password')
if bool(WEB_USER) != bool(WEB_PASSWORD):
    raise ValueError('Set both EDITH_WEB_USER and EDITH_WEB_PASSWORD')

LMSTUDIO_URL = base_url(os.getenv('LMSTUDIO_URL', 'http://127.0.0.1:1234'))
LMSTUDIO_MODE = os.getenv('LMSTUDIO_MODE', 'auto').lower()
if LMSTUDIO_MODE not in ('off', 'auto'):
    raise ValueError('LMSTUDIO_MODE must be off or auto')
MODEL = os.getenv('LMSTUDIO_MODEL', '').strip()


def seconds(name: str, default: str) -> float:
    value = float(os.getenv(name, default))
    if not 0 < value <= 300:
        raise ValueError(f'{name} must be greater than 0 and at most 300 seconds')
    return value


DEVICE_TIMEOUT = seconds('DEVICE_TIMEOUT', '3')
LMSTUDIO_API_KEY = os.getenv('LMSTUDIO_API_KEY', '').strip()
LMSTUDIO_TIMEOUT = seconds('LMSTUDIO_TIMEOUT', '90')

REPLIES = {
    'normal': "I'm EDITH. Rule mode is ready. Tell me how you're feeling, or ask me something.",
    'sad': "That sounds difficult. Want to tell me what happened?",
    'angry': "That sounds frustrating. Want to work through what happened?",
    'sleepy': "Sounds like you could use a break. Want to wrap up one small thing first?",
    'uwu': "UwU! Cozy companion mode activated.",
    'happy': "That sounds like a bright moment! Tell me more.",
    'thinking': "Let's break it into smaller steps. What are you trying to work out?",
    'curious': "Let's explore that. Rule mode has fixed replies; enable LM Studio for open-ended answers.",
}


class Message(BaseModel):
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    utc_offset: int | None = Field(default=None, ge=-720, le=840)
    message: str = Field(min_length=1, max_length=2000, pattern=r'\S')
    history: list[Message] = Field(default_factory=list, max_length=12)


class MoodRequest(BaseModel):
    name: Mood


def model_headers() -> dict:
    return {'Authorization': 'Bearer ' + LMSTUDIO_API_KEY} if LMSTUDIO_API_KEY else {}


def failure(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return 'Request timed out. Check power, Wi-Fi, IP, or model loading.'
    if isinstance(exc, httpx.HTTPStatusError):
        return f'Remote server returned HTTP {exc.response.status_code}.'
    return 'Connection failed or response was invalid. Check the address and service.'


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ignore proxy environment variables for local/LAN device traffic.
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as client:
        app.state.client = client
        app.state.action_lock = asyncio.Lock()
        database = Path(os.getenv('EDITH_STATE_DB', str(ROOT / 'data' / 'device.sqlite3')))
        database.parent.mkdir(parents=True, exist_ok=True)
        app.state.mailbox = Mailbox(database)
        app.state.panel = Companion(database)
        app.state.weather_lock = asyncio.Lock()
        app.state.transport = DEVICE_TRANSPORT
        app.state.local_command = {'command_id': None, 'desired_mood': 'normal'}
        worker = asyncio.create_task(weather_loop(app, sync_local))
        try:
            yield
        finally:
            worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker


app = FastAPI(title='EDITH Milestone 5', lifespan=lifespan)


@app.middleware('http')
async def access_control(request: Request, call_next):
    # Device authentication is independent of browser credentials.
    path = request.url.path
    if path == '/healthz':
        return JSONResponse({'ok': True})
    if path.startswith('/api/device/'):
        expected = 'Bearer ' + DEVICE_TOKEN
        supplied = request.headers.get('authorization', '')
        if DEVICE_TRANSPORT != 'poll' or not DEVICE_TOKEN or not secrets.compare_digest(supplied.encode(), expected.encode()):
            return JSONResponse({'error': 'Unauthorized device'}, status_code=401)
    elif WEB_USER:
        supplied = request.headers.get('authorization', '')
        try:
            scheme, encoded = supplied.split(' ', 1)
            decoded = base64.b64decode(encoded, validate=True).decode('utf-8')
            username, password = decoded.split(':', 1)
            valid = (scheme.lower() == 'basic'
                     and secrets.compare_digest(username.encode(), WEB_USER.encode())
                     and secrets.compare_digest(password.encode(), WEB_PASSWORD.encode()))
        except (ValueError, UnicodeError):
            valid = False
        if not valid:
            return Response(status_code=401, headers={'WWW-Authenticate': 'Basic realm="EDITH"'})
        # Reject browser cross-origin mutations. No CORS access is enabled.
        origin = request.headers.get('origin')
        if request.method == 'POST' and origin:
            from urllib.parse import urlsplit
            if urlsplit(origin).netloc != request.headers.get('host'):
                return Response(status_code=403)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@app.post('/api/device/poll')
async def poll_device(request: Request):
    ack = request.headers.get('x-edith-ack', '')
    reported = request.headers.get('x-edith-mood', 'normal')
    try:
        pending = app.state.mailbox.poll(ack, reported)
    except ValueError:
        return JSONResponse({'error': 'Invalid device report'}, status_code=422)
    if pending is None:
        return Response(status_code=204)
    # Tiny fixed protocol avoids another firmware JSON library.
    return PlainTextResponse(pending[0] + '\n' + pending[1])



async def device(path: str, params=None) -> dict:
    if DEVICE_TRANSPORT == 'poll':
        if path == '/mood':
            command = app.state.mailbox.enqueue(params['name'])
            return {'ok': True, 'configured': True, 'queued': True,
                    'response': {'command_id': command, 'mood': params['name'], 'delivery': 'queued; not yet acknowledged'}}
        state = app.state.mailbox.status()
        return {'ok': state['online'], 'configured': True, 'response': state,
                'error': None if state['online'] else 'Device has not polled in the last 20 seconds.'}
    if not DEVICE_URL:
        return {'ok': False, 'configured': False, 'error': 'Set EDITH_IP in .env and restart.'}
    try:
        if path == '/mood':
            app.state.local_command = {'command_id': str(uuid.uuid4()), 'desired_mood': params['name']}
        response = await app.state.client.get(DEVICE_URL + path, params=params, timeout=DEVICE_TIMEOUT)
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError:
            payload = response.text[:2000]
        return {'ok': True, 'configured': True, 'response': payload}
    except httpx.HTTPError as exc:
        return {'ok': False, 'configured': True, 'error': failure(exc)}


@app.get('/')
async def index():
    return FileResponse(ROOT / 'index.html')


@app.get('/api/status')
async def status():
    return {'name': 'EDITH', 'device_url': DEVICE_URL if DEVICE_TRANSPORT == 'local' else None, 'transport': DEVICE_TRANSPORT,
            'device': await device('/status'), 'moods': MOODS,
            'lmstudio_mode': LMSTUDIO_MODE, 'lmstudio_model': MODEL, 'companion': app.state.panel.snapshot()}


@app.get('/api/lmstudio')
async def lmstudio_status():
    try:
        response = await app.state.client.get(LMSTUDIO_URL + '/v1/models', headers=model_headers(), timeout=3)
        response.raise_for_status()
        models = [m['id'] for m in response.json()['data']]
        return {'ok': True, 'models': models, 'selected': MODEL, 'mode': LMSTUDIO_MODE}
    except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError) as exc:
        return {'ok': False, 'error': failure(exc), 'mode': LMSTUDIO_MODE}


@app.post('/api/mood')
async def set_mood(body: MoodRequest):
    async with app.state.action_lock:
        app.state.panel.screen('face')
        result = await device('/mood', {'name': body.name})
        await sync_local()
        return {'mood': body.name, 'device': result}


@app.post('/api/chat')
async def chat(body: ChatRequest):
    # Serialize hardware actions so simultaneous chats cannot restore stale faces.
    async with app.state.action_lock:
        if body.utc_offset is not None: app.state.panel.update(utc_offset=body.utc_offset)
        command = parse_command(body.message)
        if command:
            if command[0] == 'screen':
                app.state.panel.screen(command[1])
                reply = 'Dashboard on. The clock and timers stay active.' if command[1] == 'dashboard' else 'I am awake!'
            elif command[0] == 'timer':
                app.state.panel.timer(command[1])
                if command[1]: app.state.panel.screen('dashboard')
                reply = f'Timer started for {command[1]} seconds.' if command[1] else 'Timer cleared.'
            else:
                reply = command[1]
            if app.state.panel.read()['mode'] == 'face': app.state.panel.speak(reply)
            result = await sync_local()
            return {'reply': reply, 'source':'control', 'emotion': {'mood':'normal', 'method':'control', 'matches':[], 'reason':'Explicit device command.'},
                    'device': result, 'warning':None, 'thinking_device':None, 'companion':app.state.panel.snapshot()}
        app.state.panel.screen('face')
        detection = detect(body.message, body.history)
        mood = detection['mood']
        reply, source, warning = REPLIES[mood], 'rules', None
        thinking = None
        try:
            if LMSTUDIO_MODE == 'auto':
                thinking = await device('/mood', {'name': 'thinking'})
                try:
                    if not MODEL:
                        raise ValueError('Set LMSTUDIO_MODEL to the exact server model ID.')
                    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
                    messages += [m.model_dump() for m in body.history]
                    messages.append({'role': 'user', 'content': body.message})
                    response = await app.state.client.post(LMSTUDIO_URL + '/v1/chat/completions', headers=model_headers(),
                        json={'model': MODEL, 'messages': messages, 'stream': False,
                              'max_tokens': 500, 'temperature': 0.3, 'response_format': RESPONSE_FORMAT},
                        timeout=httpx.Timeout(LMSTUDIO_TIMEOUT, connect=3))
                    response.raise_for_status()
                    content = response.json()['choices'][0]['message']['content']
                    if not isinstance(content, str) or not content.strip():
                        raise ValueError('Empty model reply')
                    reply, detection = parse_model(content)
                    mood = detection['mood']
                    source = 'lmstudio'
                except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError) as exc:
                    warning = (str(exc) if isinstance(exc, ValueError) else failure(exc)) + ' Using a fixed rule-based reply.'
        finally:
            app.state.panel.speak(reply)
            final_device = await device('/mood', {'name': mood})
            await sync_local()
        return {'reply': reply, 'source': source, 'emotion': detection,
                'device': final_device, 'thinking_device': thinking, 'warning': warning}


class ScreenRequest(BaseModel):
    mode: Literal['face', 'dashboard', 'stopwatch']
    utc_offset: int | None = Field(default=None, ge=-720, le=840)

class TimerRequest(BaseModel):
    utc_offset: int | None = Field(default=None, ge=-720, le=840)
    seconds: int = Field(ge=0, le=86400, strict=True)

class DashboardRequest(BaseModel):
    city: str = Field(min_length=1, max_length=80)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    utc_offset: int = Field(ge=-720, le=840)

async def sync_local():
    if DEVICE_TRANSPORT == 'poll':
        return {'ok':True, 'queued':True, 'response':{'delivery':'Settings saved; awaiting firmware v2 polling.'}}
    if not DEVICE_URL:
        return {'ok':False, 'error':'Set EDITH_IP to use the OLED.'}
    try:
        response = await app.state.client.post(DEVICE_URL+'/companion',
            content=app.state.panel.wire(app.state.local_command),
            headers={'Content-Type':'text/plain'}, timeout=DEVICE_TIMEOUT)
        response.raise_for_status()
        return {'ok':True, 'response':'Settings delivered to firmware.'}
    except httpx.HTTPError:
        return {'ok':False, 'error':'Companion settings not delivered. Check device/network and upload firmware v2.'}

@app.post('/api/device/poll-v2')
async def poll_device_v2(request: Request):
    try:
        app.state.mailbox.poll(request.headers.get('x-edith-ack',''), request.headers.get('x-edith-mood','normal'))
        app.state.mailbox.telemetry(2, request.headers.get('x-edith-mode','face'))
    except ValueError:
        return JSONResponse({'error':'Invalid device report'}, status_code=422)
    return PlainTextResponse(app.state.panel.wire(app.state.mailbox.status()))

@app.post('/api/screen')
async def screen(body: ScreenRequest):
    app.state.panel.screen(body.mode, body.utc_offset)
    return {'companion':app.state.panel.snapshot(), 'device':await sync_local()}

@app.post('/api/timer')
async def timer(body: TimerRequest):
    if body.utc_offset is not None: app.state.panel.update(utc_offset=body.utc_offset)
    app.state.panel.timer(body.seconds)
    if body.seconds: app.state.panel.screen('dashboard')
    return {'companion':app.state.panel.snapshot(), 'device':await sync_local()}

class StopwatchRequest(BaseModel):
    action: Literal['start', 'pause', 'reset']

class AlarmRequest(BaseModel):
    at: int | None = Field(default=None, strict=True)
    utc_offset: int | None = Field(default=None, ge=-720, le=840)

@app.post('/api/stopwatch')
async def stopwatch(body: StopwatchRequest):
    async with app.state.action_lock:
        app.state.panel.stopwatch(body.action)
        return {'companion':app.state.panel.snapshot(), 'device':await sync_local()}

@app.post('/api/alarm')
async def alarm(body: AlarmRequest):
    if body.at is not None and not time.time() < body.at <= time.time() + 7*86400:
        return JSONResponse({'error':'Choose a future alarm within the next 7 days.'}, status_code=422)
    async with app.state.action_lock:
        if body.utc_offset is not None: app.state.panel.update(utc_offset=body.utc_offset)
        app.state.panel.alarm(body.at)
        return {'companion':app.state.panel.snapshot(), 'device':await sync_local()}

@app.get('/api/locations')
async def locations(q: str = ''):
    if not 2 <= len(q.strip()) <= 80:
        return JSONResponse({'error':'Enter a city name between 2 and 80 characters.'}, status_code=422)
    try:
        response = await app.state.client.get('https://geocoding-api.open-meteo.com/v1/search',
            params={'name':q.strip(), 'count':5, 'language':'en', 'format':'json'}, timeout=5)
        response.raise_for_status()
        results = response.json().get('results', [])
        return {'results':[{'city':', '.join(filter(None,[r['name'],r.get('admin1'),r.get('country')])),
                            'latitude':r['latitude'], 'longitude':r['longitude']} for r in results]}
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return JSONResponse({'error':'City lookup unavailable. Try again later.'}, status_code=502)

@app.post('/api/dashboard')
async def dashboard(body: DashboardRequest):
    app.state.panel.update(city=body.city, latitude=body.latitude, longitude=body.longitude,
                           utc_offset=body.utc_offset, weather=None, weather_attempt=0)
    await refresh_weather(app, force=True)
    return {'companion':app.state.panel.snapshot(), 'device':await sync_local()}
