from fastapi.testclient import TestClient
import app as edith

def test_poll_api_auth_delivery_and_ack(monkeypatch, tmp_path):
    monkeypatch.setattr(edith, 'DEVICE_TRANSPORT', 'poll')
    monkeypatch.setattr(edith, 'DEVICE_TOKEN', 'd' * 48)
    monkeypatch.setattr(edith, 'WEB_USER', 'edith')
    monkeypatch.setattr(edith, 'WEB_PASSWORD', 'p' * 32)
    monkeypatch.setattr(edith, 'LMSTUDIO_MODE', 'off')
    monkeypatch.setenv('EDITH_STATE_DB', str(tmp_path / 'device.sqlite3'))
    with TestClient(edith.app) as client:
        assert client.get('/healthz').status_code == 200
        assert client.get('/').status_code == 401
        assert client.get('/docs').status_code == 401
        assert client.post('/api/device/poll').status_code == 401
        auth = ('edith', 'p' * 32)
        assert client.get('/', auth=auth).status_code == 200
        assert client.post('/api/mood', json={'name':'happy'}, auth=auth,
                           headers={'Origin':'https://other.test'}).status_code == 403
        headers = {'Authorization': 'Bearer ' + 'd' * 48, 'X-Edith-Mood':'normal'}
        assert client.post('/api/device/poll', headers=headers).status_code == 204
        result = client.post('/api/chat', json={'message':'I am sad'}, auth=auth).json()
        assert result['device']['queued']
        assert not client.get('/api/status', auth=auth).json()['device']['response']['applied']
        command = client.post('/api/device/poll', headers=headers)
        assert command.status_code == 200
        command_id, mood = command.text.split('\n')
        assert mood == 'sad'
        headers.update({'X-Edith-Ack':command_id, 'X-Edith-Mood':'sad'})
        assert client.post('/api/device/poll', headers=headers).status_code == 204
        assert client.get('/api/status', auth=auth).json()['device']['response']['applied']
        headers['X-Edith-Mood'] = 'invalid'
        assert client.post('/api/device/poll', headers=headers).status_code == 422
