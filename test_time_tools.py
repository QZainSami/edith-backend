import json
import sqlite3
import time
from fastapi.testclient import TestClient
import app as edith
from companion import Companion

def test_stopwatch_pause_resume_persistence_and_wire(tmp_path):
    now = [1800000000.0]
    panel = Companion(tmp_path/'state.db', lambda: now[0])
    panel.stopwatch('start')
    now[0] += 12.5
    assert panel.snapshot()['stopwatch_elapsed_ms'] == 12500
    panel.stopwatch('pause')
    now[0] += 40
    assert panel.snapshot()['stopwatch_elapsed_ms'] == 12500
    restored = Companion(panel.path, lambda: now[0])
    assert not restored.snapshot()['stopwatch_running']
    restored.stopwatch('start'); now[0] += 2
    assert restored.snapshot()['stopwatch_elapsed_ms'] == 14500
    assert restored.snapshot()['mode'] == 'stopwatch'
    fields = restored.wire({}).splitlines()
    assert fields[16] == 'TOOLS1' and fields[18:20] == ['14500','1']
    assert len(restored.wire({})) < 512
    restored.timer(86400); restored.speak('Hello EDITH'); restored.alarm(now[0]+7*86400)
    assert len(restored.wire({'command_id':'a'*36,'desired_mood':'thinking'})) < 512
    restored.stopwatch('reset')
    assert restored.snapshot()['stopwatch_elapsed_ms'] == 0
    assert not restored.snapshot()['stopwatch_running']

def test_alarm_survives_restart_and_stays_due_until_dismissed(tmp_path):
    now = [1800000000.0]
    panel = Companion(tmp_path/'state.db',lambda: now[0])
    panel.alarm(now[0]+60)
    now[0] += 10
    assert Companion(panel.path,lambda:now[0]).snapshot()['alarm_remaining_ms'] == 50000
    now[0] += 60
    assert panel.snapshot()['alarm_due']
    panel.alarm(None)
    assert panel.snapshot()['alarm_remaining_ms'] == -1

def test_legacy_companion_state_accepts_time_tools(tmp_path):
    panel = Companion(tmp_path/'state.db')
    with sqlite3.connect(panel.path) as db:
        db.execute('UPDATE companion SET body=?', (json.dumps({'mode':'face','revision':'old','timer_id':'','timer_deadline':0,
            'speech_id':'','speech_end':0,'weather':None,'utc_offset':0,'city':''}),))
    assert panel.snapshot()['stopwatch_elapsed_ms'] == 0
    assert panel.snapshot()['alarm_remaining_ms'] == -1
    panel.stopwatch('start')
    assert panel.snapshot()['stopwatch_running']

def test_time_tool_api_validation(monkeypatch):
    monkeypatch.setattr(edith,'DEVICE_TRANSPORT','poll')
    with TestClient(edith.app) as client:
        assert client.post('/api/stopwatch',json={'action':'lap'}).status_code == 422
        for action in ('start','pause','reset'):
            assert client.post('/api/stopwatch',json={'action':action}).status_code == 200
        for value in (int(time.time())-1,int(time.time())+8*86400,1.5):
            assert client.post('/api/alarm',json={'at':value}).status_code == 422
        result = client.post('/api/alarm',json={'at':int(time.time())+60}).json()
        assert result['companion']['alarm_remaining_ms'] > 0
        assert client.post('/api/alarm',json={'at':None}).json()['companion']['alarm_remaining_ms'] == -1
