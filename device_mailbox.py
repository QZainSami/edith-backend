"""Single-device command mailbox. SQLite survives process restarts on persistent disks."""
import sqlite3
from contextlib import contextmanager
import time
import uuid

MOODS = ('normal', 'happy', 'sad', 'angry', 'sleepy', 'curious', 'thinking', 'uwu')

class Mailbox:
    def __init__(self, path, clock=time.time):
        self.path, self.clock = str(path), clock
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS state (slot INTEGER PRIMARY KEY, command TEXT, desired TEXT, expires REAL, ack TEXT, reported TEXT, seen REAL)')
            db.execute("INSERT OR IGNORE INTO state VALUES (1, '', 'normal', 0, '', 'normal', 0)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=3)
        try:
            with db:
                yield db
        finally:
            db.close()

    def enqueue(self, mood):
        if mood not in MOODS:
            raise ValueError('Invalid mood')
        command = str(uuid.uuid4())
        with self.connect() as db:
            db.execute('UPDATE state SET command=?, desired=?, expires=? WHERE slot=1',
                       (command, mood, self.clock() + (30 if mood == 'thinking' else 120)))
        return command

    def poll(self, ack, reported):
        if reported not in MOODS or len(ack) > 36:
            raise ValueError('Invalid device report')
        with self.connect() as db:
            db.execute('UPDATE state SET ack=?, reported=?, seen=? WHERE slot=1', (ack, reported, self.clock()))
            command, mood, expires = db.execute('SELECT command, desired, expires FROM state WHERE slot=1').fetchone()
        return (command, mood) if command and command != ack and expires > self.clock() else None

    def status(self):
        with self.connect() as db:
            command, desired, expires, ack, reported, seen = db.execute('SELECT command, desired, expires, ack, reported, seen FROM state WHERE slot=1').fetchone()
        online = seen > 0 and self.clock() - seen < 20
        applied = bool(command and command == ack and reported == desired)
        return {'online': online, 'mood': reported, 'desired_mood': desired,
                'command_id': command or None, 'applied': applied,
                'pending': bool(command and not applied and expires > self.clock()),
                'expired': bool(command and not applied and expires <= self.clock()),
                'last_seen_seconds': round(max(0, self.clock() - seen), 1) if seen else None}
