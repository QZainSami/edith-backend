import os
import json
import asyncio
from contextlib import contextmanager
os.environ['EDITH_IP'] = 'http://edith.test'
os.environ['LMSTUDIO_MODE'] = 'off'

import httpx
from fastapi.testclient import TestClient
import app as edith


@contextmanager
def mocked_remote(handler):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        yield client
    finally:
        asyncio.run(client.aclose())


def test_rules():
    assert edith.detect('I am unhappy')['mood'] == 'sad'
    assert edith.detect('not happy')['mood'] == 'normal'
    assert edith.detect('How?')['mood'] == 'curious'
    assert edith.detect('happy but sad')['mood'] == 'sad'
    assert edith.detect('uwu')['mood'] == 'uwu'
    assert edith.detect('think about it')['mood'] == 'thinking'


def test_device_and_validation(monkeypatch):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, text='OK')
    with TestClient(edith.app) as client:
        with mocked_remote(handler) as remote:
            edith.app.state.client = remote
            assert client.get('/').status_code == 200
            assert client.get('/api/status').json()['device']['ok']
            for mood in edith.MOODS:
                assert client.post('/api/mood', json={'name': mood}).json()['device']['ok']
                assert [r for r in calls if r.url.path == '/mood'][-1].url.params['name'] == mood
            assert client.post('/api/mood', json={'name': 'invalid'}).status_code == 422
            assert client.post('/api/chat', json={'message': '   '}).status_code == 422
            assert client.post('/api/chat', json={'message': 'x' * 2001}).status_code == 422


def test_unconfigured(monkeypatch):
    monkeypatch.setattr(edith, 'DEVICE_URL', '')
    with TestClient(edith.app) as client:
        result = client.post('/api/chat', json={'message': 'happy'}).json()
        assert result['source'] == 'rules'
        assert not result['device']['configured']


def test_network_failure(monkeypatch):
    def handler(request):
        raise httpx.ConnectError('offline', request=request)
    with TestClient(edith.app) as client:
        with mocked_remote(handler) as remote:
            edith.app.state.client = remote
            result = client.post('/api/chat', json={'message': 'happy'}).json()
            assert result['reply']
            assert not result['device']['ok']


def test_lmstudio_success_and_fallback(monkeypatch):
    monkeypatch.setattr(edith, 'LMSTUDIO_MODE', 'auto')
    monkeypatch.setattr(edith, 'MODEL', 'test-gemma')
    calls = []
    def handler(request):
        calls.append(request)
        if request.url.path == '/v1/chat/completions':
            return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps({'reply': 'Here for you 💚', 'mood': 'sad', 'reason': 'User is sad.'})}}]})
        return httpx.Response(200, json={'mood': 'ok'})
    with TestClient(edith.app) as client:
        with mocked_remote(handler) as remote:
            edith.app.state.client = remote
            result = client.post('/api/chat', json={'message': 'sad'}).json()
            assert result['source'] == 'lmstudio'
            assert result['reply'] == 'Here for you 💚'
            assert calls[0].url.params['name'] == 'thinking'
            assert [r for r in calls if r.url.path == '/mood'][-1].url.params['name'] == 'sad'
        def timeout(request):
            if request.url.path == '/v1/chat/completions':
                raise httpx.ReadTimeout('slow', request=request)
            return httpx.Response(200, text='OK')
        with mocked_remote(timeout) as remote:
            edith.app.state.client = remote
            result = client.post('/api/chat', json={'message': 'happy'}).json()
            assert result['source'] == 'rules'
            assert result['warning']
            assert result['device']['ok']
