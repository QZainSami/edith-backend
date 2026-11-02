"""Persistent dashboard/timer state and compact v2 OLED protocol."""
import json
import math
import re
import sqlite3
import time
import unicodedata
import uuid

class Companion:
    def __init__(self, path, clock=time.time):
        self.path, self.clock = str(path), clock
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS companion (slot INTEGER PRIMARY KEY, body TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO companion VALUES (1, ?)', (json.dumps({
                'mode': 'face', 'revision': str(uuid.uuid4()), 'utc_offset': 0,
                'city': '', 'latitude': None, 'longitude': None, 'weather': None,
                'weather_attempt': 0, 'weather_error': None,
                'timer_id': '', 'timer_deadline': 0, 'speech_id': '', 'speech_end': 0}),))

    def read(self):
        db = sqlite3.connect(self.path)
        try:
            return json.loads(db.execute('SELECT body FROM companion WHERE slot=1').fetchone()[0])
        finally:
            db.close()

    def update(self, **changes):
        db = sqlite3.connect(self.path)
        try:
            with db:
                db.execute('BEGIN IMMEDIATE')
                state = json.loads(db.execute('SELECT body FROM companion WHERE slot=1').fetchone()[0])
                state.update(changes)
                state['revision'] = str(uuid.uuid4())
                db.execute('UPDATE companion SET body=? WHERE slot=1', (json.dumps(state),))
            return state
        finally:
            db.close()

    def screen(self, mode, utc_offset=None):
        changes = {'mode': mode, 'speech_end': 0}
        if utc_offset is not None: changes['utc_offset'] = utc_offset
        return self.update(**changes)

    def timer(self, seconds):
        return self.update(timer_id=str(uuid.uuid4()) if seconds else '',
                           timer_deadline=self.clock() + seconds if seconds else 0)

    def speak(self, reply):
        duration = max(1500, min(20000, len(reply.split()) * 330))
        self.update(speech_id=str(uuid.uuid4()), speech_end=self.clock()+duration/1000)

    def snapshot(self):
        state = self.read()
        now = self.clock()
        state['now'] = int(now)
        state['timer_remaining_ms'] = max(0, math.ceil((state['timer_deadline']-now)*1000)) if state['timer_id'] else -1
        state['timer_done'] = bool(state['timer_id'] and state['timer_remaining_ms'] == 0)
        state['speech_remaining_ms'] = max(0, min(20000, int((state['speech_end']-now)*1000)))
        state['weather_age'] = max(0, int(now-state['weather']['fetched_at'])) if state['weather'] else -1
        return state

    def wire(self, mailbox):
        state = self.snapshot()
        weather = state['weather'] or {}
        city = unicodedata.normalize('NFKD', state['city']).encode('ascii', 'ignore').decode()
        city = re.sub(r'[^A-Za-z0-9 .,-]', '', city)[:16] or 'Set city in UI'
        # Expired unacknowledged faces must never be replayed. Other settings persist.
        command = mailbox.get('command_id') if not mailbox.get('expired') else None
        lines = ['EDITH2', command or '-', mailbox.get('desired_mood', 'normal'),
                 state['revision'], state['mode'], state['speech_id'] or '-',
                 state['speech_remaining_ms'], state['now'], state['utc_offset'], city,
                 weather.get('code', -1), round(weather.get('temperature', -999.9)*10),
                 weather.get('humidity', -1), state['weather_age'],
                 state['timer_id'] or '-', state['timer_remaining_ms']]
        return '\n'.join(map(str, lines)) + '\n'


def parse_command(text):
    """Deliberately small grammar; ordinary conversation is never executed as a tool."""
    text = text.lower().strip().rstrip('.!?').strip()
    text = re.sub(r'^edith[, ]+', '', text)
    if text in ('sleep', 'go to sleep', 'sleep mode'): return ('screen', 'dashboard')
    if text in ('wake', 'wake up', 'wake mode'): return ('screen', 'face')
    if text in ('cancel timer', 'stop timer', 'clear timer'): return ('timer', 0)
    match = re.fullmatch(r'(?:set |start )?(?:a )?timer(?: for)? (\d+(?:\.\d+)?)\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h)', text)
    if match:
        unit = match[2][0]
        seconds = round(float(match[1]) * {'s':1, 'm':60, 'h':3600}[unit])
        if not 1 <= seconds <= 86400: return ('invalid', 'Timers must be between 1 second and 24 hours.')
        return ('timer', seconds)
    return None
