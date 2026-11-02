"""Open-Meteo weather: bounded requests, cached readings, explicit stale/error state."""
import asyncio
import math
import time
import httpx

async def refresh_weather(app, force=False):
    async with app.state.weather_lock:
        panel = app.state.panel
        settings = panel.read()
        if settings['latitude'] is None: return
        if not force and time.time()-settings['weather_attempt'] < 600: return
        panel.update(weather_attempt=time.time())
        try:
            response = await app.state.client.get('https://api.open-meteo.com/v1/forecast',
                params={'latitude': settings['latitude'], 'longitude': settings['longitude'],
                        'current':'temperature_2m,relative_humidity_2m,weather_code'}, timeout=5)
            response.raise_for_status()
            data = response.json()['current']
            temperature = float(data['temperature_2m'])
            humidity, code = int(data['relative_humidity_2m']), int(data['weather_code'])
            if not math.isfinite(temperature) or not -100 <= temperature <= 80 or not 0 <= humidity <= 100 or not 0 <= code <= 99:
                raise ValueError('Invalid weather values')
            current = panel.read()
            if (current['latitude'], current['longitude']) == (settings['latitude'], settings['longitude']):
                panel.update(weather={'temperature':temperature, 'humidity':humidity,
                                      'code':code, 'fetched_at':time.time()}, weather_error=None)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            panel.update(weather_error='Weather unavailable; last reading may be stale.')

async def weather_loop(app, sync_local):
    while True:
        try:
            await refresh_weather(app)
            if app.state.transport == 'local' and (app.state.local_command['command_id'] or app.state.panel.read()['mode'] == 'dashboard'):
                await sync_local()
        except (httpx.HTTPError, ValueError, OSError):
            pass
        await asyncio.sleep(5)
