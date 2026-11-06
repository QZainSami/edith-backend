import json
import pytest
from emotion import detect, parse_model, MOODS
from device_mailbox import Mailbox


@pytest.mark.parametrize('mood,message', [('shy', 'I feel shy'), ('blush', 'You made me blush'), ('unknown', 'Feeling cheeky')])
def test_new_expression_survives_detection_and_delivery(tmp_path, mood, message):
    assert mood in MOODS
    assert detect(message)['mood'] == mood
    _, result = parse_model(json.dumps({'reply': 'Hello!', 'mood': mood, 'reason': 'Playful expression'}))
    assert result['mood'] == mood
    mailbox = Mailbox(str(tmp_path / 'expressions.sqlite3'))
    command = mailbox.enqueue(mood)
    assert mailbox.poll('', 'normal') == (command, mood)
    assert mailbox.poll(command, mood) is None
    assert mailbox.status()['applied']
