"""Deterministic offline test configuration on Windows and Linux.

Applied before test modules import app; private .env values must not change tests.
Individual tests can enable poll mode or mock model generation with monkeypatch.
"""
import os

os.environ.update({
    'EDITH_IP': 'http://edith.test',
    'DEVICE_TRANSPORT': 'local',
    'LMSTUDIO_MODE': 'off',
    'LMSTUDIO_URL': 'http://127.0.0.1:1234',
    'LMSTUDIO_API_KEY': '',
    'EDITH_WEB_USER': '',
    'EDITH_WEB_PASSWORD': '',
    'EDITH_DEVICE_TOKEN': '',
})
