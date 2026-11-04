"""Deterministic offline test configuration on Windows and Linux.

Applied before test modules import app; private .env values must not change tests.
Individual tests can enable poll mode or mock model generation with monkeypatch.
"""
import os

os.environ.update({
    'LLM_PROVIDER':'lmstudio',
    'GEMINI_API_KEY':'',
    'DATABASE_URL':'',
    'RENDER':'false',
    'EDITH_IP': 'http://edith.test',
    'DEVICE_TRANSPORT': 'local',
    'LMSTUDIO_MODE': 'off',
    'LMSTUDIO_URL': 'http://127.0.0.1:1234',
    'LMSTUDIO_API_KEY': '',
    'EDITH_WEB_USER': '',
    'EDITH_WEB_PASSWORD': '',
    'EDITH_DEVICE_TOKEN': '',
})


import pytest

@pytest.fixture(autouse=True)
def isolated_state_database(monkeypatch, tmp_path):
    monkeypatch.setenv('EDITH_STATE_DB', str(tmp_path / 'device.sqlite3'))
