import asyncio
import sqlite3
import pytest
from companion import Companion, parse_command
from device_mailbox import Mailbox
from fastapi.testclient import TestClient
import httpx
import app as edith
from weather_service import refresh_weather

@pytest.mark.parametrize('text,expected',[
    ('EDITH sleep',('screen','dashboard')), ('go to sleep',('screen','dashboard')),
    ('EDITH, wake up!',('screen','face')), ('set a timer for 5 minutes',('timer',300)),
    ('timer 30 seconds',('timer',30)), ('start a timer for 1.5 hours',('timer',5400)),
    ('cancel timer',('timer',0)), ('I feel sleepy',None), ('what is a timer?',None),
])
def test_command_grammar(text,expected):
    assert parse_command(text)==expected


def test_persisted_timer_wire_and_speech(tmp_path):
    now=[1800000000.0]
    box=Mailbox(tmp_path/'state.db',lambda:now[0])
    panel=Companion(tmp_path/'state.db',lambda:now[0])
    panel.screen('dashboard',300);panel.timer(60)
    now[0]+=12
    assert panel.snapshot()['timer_remaining_ms']==48000
    restored=Companion(tmp_path/'state.db',lambda:now[0])
    assert restored.snapshot()['mode']=='dashboard'
    assert restored.snapshot()['timer_remaining_ms']==48000
    fields=panel.wire(box.status()).splitlines()
    assert len(fields)==16 and fields[0]=='EDITH2' and fields[8]=='300'
    now[0]+=50
    assert panel.snapshot()['timer_done']
    panel.timer(0)
    assert panel.snapshot()['timer_remaining_ms']==-1
    panel.speak('Hello there')
    speech_id=panel.read()['speech_id']
    assert panel.snapshot()['speech_remaining_ms']>0
    now[0]+=30
    assert panel.snapshot()['speech_remaining_ms']==0
    assert panel.read()['speech_id']==speech_id


def test_migrates_old_mailbox(tmp_path):
    path=tmp_path/'old.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE state (slot INTEGER PRIMARY KEY, command TEXT, desired TEXT, expires REAL, ack TEXT, reported TEXT, seen REAL)')
        db.execute("INSERT INTO state VALUES (1,'old','sad',0,'old','sad',1)")
    box=Mailbox(path)
    assert box.status()['mood']=='sad'
    box.telemetry(2,'dashboard')
    assert box.status()['protocol']==2


def test_control_endpoints_and_v2(monkeypatch):
    monkeypatch.setattr(edith,'DEVICE_TRANSPORT','poll')
    monkeypatch.setattr(edith,'DEVICE_TOKEN','d'*48)
    with TestClient(edith.app) as client:
        assert client.post('/api/device/poll-v2').status_code==401
        assert client.post('/api/timer',json={'seconds':-1}).status_code==422
        assert client.post('/api/timer',json={'seconds':86401}).status_code==422
        assert client.post('/api/timer',json={'seconds':1.5}).status_code==422
        assert client.post('/api/screen',json={'mode':'deep-sleep'}).status_code==422
        for text in ('EDITH sleep','wake up','set a timer for 30 seconds'):
            response=client.post('/api/chat',json={'message':text,'utc_offset':300}).json()
            assert response['source']=='control'
        state=client.get('/api/status').json()['companion']
        assert state['mode']=='dashboard' and state['timer_remaining_ms']>0
        headers={'Authorization':'Bearer '+'d'*48,'X-Edith-Mood':'normal','X-Edith-Mode':'dashboard'}
        packet=client.post('/api/device/poll-v2',headers=headers)
        assert packet.status_code==200 and len(packet.text.splitlines())==16
        assert client.get('/api/status').json()['device']['response']['protocol']==2
        client.post('/api/timer',json={'seconds':0})
        assert client.get('/api/status').json()['companion']['timer_remaining_ms']==-1


def test_weather_success_cache_and_failure(tmp_path):
    panel=Companion(tmp_path/'weather.db')
    panel.update(city='Test City',latitude=10,longitude=20)
    class State: pass
    class FakeApp: pass
    instance=FakeApp();instance.state=State();instance.state.panel=panel
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(200,json={'current':{'temperature_2m':25,'relative_humidity_2m':40,'weather_code':0}})
    async def run():
        instance.state.weather_lock=asyncio.Lock()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as remote:
            instance.state.client=remote
            await refresh_weather(instance)
            await refresh_weather(instance)
            assert len(calls)==1
            assert panel.snapshot()['weather']['temperature']==25
        def fail(request): raise httpx.ConnectError('offline',request=request)
        async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as remote:
            instance.state.client=remote
            await refresh_weather(instance,force=True)
            assert panel.snapshot()['weather_error']
            assert panel.snapshot()['weather']['temperature']==25
    asyncio.run(run())
