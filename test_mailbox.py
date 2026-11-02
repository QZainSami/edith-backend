import tempfile
import unittest
from pathlib import Path
from device_mailbox import Mailbox

class MailboxTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.now = 1000
        self.path = Path(self.directory.name) / 'state.sqlite3'
        self.box = Mailbox(self.path, lambda: self.now)

    def test_delivery_ack_and_restart(self):
        command = self.box.enqueue('sad')
        self.assertEqual(self.box.poll('', 'normal'), (command, 'sad'))
        self.assertFalse(self.box.status()['applied'])
        self.assertIsNone(self.box.poll(command, 'sad'))
        self.assertTrue(self.box.status()['applied'])
        self.assertTrue(Mailbox(self.path, lambda: self.now).status()['applied'])

    def test_latest_command_wins(self):
        self.box.enqueue('thinking')
        final = self.box.enqueue('happy')
        self.assertEqual(self.box.poll('', 'normal'), (final, 'happy'))

    def test_expiry_and_offline(self):
        self.box.enqueue('thinking')
        self.now += 31
        self.assertIsNone(self.box.poll('', 'normal'))
        self.assertTrue(self.box.status()['expired'])
        self.now += 21
        self.assertFalse(self.box.status()['online'])

    def test_report_validation(self):
        with self.assertRaises(ValueError): self.box.poll('', 'invalid')
        with self.assertRaises(ValueError): self.box.enqueue('invalid')

if __name__ == '__main__': unittest.main()
