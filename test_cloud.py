"""Cloud contracts without real credentials, paid requests or a remote database."""
import json
import pytest
import httpx
from fastapi.testclient import TestClient
import app as edith
from storage import Database, StorageUnavailable
from companion import Companion

@pytest.fixture
def gemini(monkeypatch):
    monkeypatch.setattr(edith, 'LLM_PROVIDER', 'gemini')
    monkeypatch.setattr(edith, 'GEMINI_API_KEY', 'test-key-not-real')
    monkeypatch.setattr(edith, 'DEVICE_TRANSPORT', 'poll')
    monkeypatch.setattr(edith, 'GEMINI_MODEL', 'gemini-3.1-flash-lite')

def test_gemini_chat_schema_history_emojis_and_legacy_status(gemini):
    calls=[]
    def handler(request):
        calls.append(request)
        assert request.url.host == 'generativelanguage.googleapis.com'
        assert request.headers['authorization'] == 'Bearer test-key-not-real'
        assert 'test-key' not in str(request.url)
        if request.url.path.endswith('/models'):
            return httpx.Response(200,json={'data':[{'id':'gemini-3.1-flash-lite'}]})
        payload=json.loads(request.content)
        assert payload['messages'][0]['role']=='system'
        assert payload['messages'][1]['content']=='Earlier conversation'
        assert payload['response_format']['json_schema']['schema']['properties']['mood']['enum']==list(edith.MOODS)
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'reply':'Here for you 💚','mood':'sad','reason':'User feels low.'})}}]})
    with TestClient(edith.app) as client:
        original=edith.app.state.client
        edith.app.state.client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            reply=client.post('/api/chat',json={'message':'I feel down','history':[{'role':'user','content':'Earlier conversation'}]}).json()
            assert reply['reply']=='Here for you 💚' and reply['source']=='gemini'
            assert reply['emotion']['method']=='gemini' and reply['emotion']['mood']=='sad'
            for path in ('/api/model','/api/lmstudio'):
                status=client.get(path).json()
                assert status['ok'] and status['provider']=='gemini' and status['mode']=='auto'
            status=client.get('/api/status').json()
            assert status['lmstudio_model']=='gemini-3.1-flash-lite' # old Android compatibility
            assert status['model_provider']=='gemini'
            assert 'test-key-not-real' not in json.dumps(status)
        finally:
            import asyncio
            asyncio.run(edith.app.state.client.aclose())
            edith.app.state.client=original

@pytest.mark.parametrize('failure',['quota','invalid','blocked','timeout'])
def test_gemini_failures_restore_a_final_face_and_rules(gemini, failure):
    def handler(request):
        if failure=='timeout': raise httpx.ReadTimeout('timeout',request=request)
        if failure=='quota': return httpx.Response(429,json={'error':{'message':'quota'}})
        if failure=='blocked': return httpx.Response(200,json={'choices':[]})
        return httpx.Response(200,json={'choices':[{'message':{'content':'{"mood":"invalid"}'}}]})
    with TestClient(edith.app) as client:
        original=edith.app.state.client
        edith.app.state.client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            reply=client.post('/api/chat',json={'message':'I am sad'}).json()
            assert reply['source']=='rules' and reply['warning']
            assert edith.app.state.mailbox.status()['desired_mood']=='sad'
        finally:
            import asyncio
            asyncio.run(edith.app.state.client.aclose())
            edith.app.state.client=original

def test_sqlite_transaction_rollback(tmp_path):
    db=Database(tmp_path/'state.db')
    panel=Companion(db); before=panel.read()
    with pytest.raises(RuntimeError):
        with db.connect(write=True) as connection:
            connection.execute('UPDATE companion SET body=?', ('broken',))
            raise RuntimeError('abort')
    assert panel.read()==before
    db.close()

def test_render_requires_persistent_database(monkeypatch):
    monkeypatch.setenv('RENDER','true')
    monkeypatch.setenv('DATABASE_URL','')
    with pytest.raises(ValueError,match='Render requires DATABASE_URL'):
        with TestClient(edith.app): pass

def test_storage_error_is_sanitized(monkeypatch):
    monkeypatch.setattr(edith,'DEVICE_TRANSPORT','poll')
    with TestClient(edith.app) as client:
        def fail(): raise StorageUnavailable('private-connection-details')
        monkeypatch.setattr(edith.app.state.panel, 'snapshot', fail)
        response=client.get('/api/status')
        assert response.status_code==503 and 'private-connection-details' not in response.text
