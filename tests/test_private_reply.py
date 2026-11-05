import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / 'ai'), str(root / 'web'), str(root / 'status')]
spec = importlib.util.spec_from_file_location('agent_app', root / 'agent_console/app.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class PrivateReplyTest(unittest.TestCase):
    def test_sender_identity_and_allowlist(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            memory = base / 'runtime/memory/wechat_memory.sqlite'
            memory.parent.mkdir(parents=True)
            source = base / 'runtime/wechat-decrypt/decrypted/message/message_0.db'
            source.parent.mkdir(parents=True)
            with sqlite3.connect(source) as db:
                db.execute('CREATE TABLE Name2Id(user_name TEXT)')
                db.executemany('INSERT INTO Name2Id VALUES (?)', [('self',), ('peer',)])
            with sqlite3.connect(memory) as db:
                db.executescript('''
                    CREATE TABLE chats(username TEXT, display_name TEXT, is_group INTEGER, sort_timestamp INTEGER, last_timestamp INTEGER);
                    CREATE TABLE messages(message_uid TEXT, chat_username TEXT, chat_display_name TEXT, type_label TEXT,
                        create_time INTEGER, local_id INTEGER, source TEXT, message_content TEXT, compress_content TEXT,
                        origin_source INTEGER, real_sender_id INTEGER, source_message_db TEXT);
                ''')
                db.executemany('INSERT INTO chats VALUES (?,?,?,?,?)', [
                    ('peer', '测试联系人', 0, 1, 1), ('other', 'Other', 0, 1, 1), ('group@chatroom', 'Group', 1, 1, 1),
                ])
                for uid, chat, sender in [('own', 'peer', 1), ('incoming', 'peer', 2), ('othermsg', 'other', 2), ('groupmsg', 'group@chatroom', 2)]:
                    db.execute('INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                               (uid, chat, '测试联系人' if chat == 'peer' else chat, 'text', 2, 2, '', 'hi', '', 2, sender, str(source)))
            cfg = {'reply_sender': {'allowed_chats': ['peer']}, 'agent': {'auto_reply_enabled': True}}
            state = {'watermarks': {x: {'create_time': 1, 'local_id': 0} for x in ['peer', 'other', 'group@chatroom']}}
            normalize = lambda row: {**row, 'is_self_message': app.is_self_message(row), 'text': 'hi'}
            with patch.object(app, 'ROOT', base), patch.object(app, 'MEMORY_DB', memory), \
                 patch.object(app, 'normalize_auto_message', side_effect=normalize), \
                 patch.object(app, 'is_bot_mention_row', return_value=False), patch.object(app, 'write_auto_reply_state'):
                self.assertTrue(app.is_private_incoming({'chat_username': 'peer', 'source_message_db': str(source), 'real_sender_id': 2}))
                self.assertFalse(app.is_private_incoming({'chat_username': 'peer', 'source_message_db': str(source), 'real_sender_id': 1}))
                self.assertFalse(app.is_private_incoming({'chat_username': 'peer', 'source_message_db': '/etc/passwd', 'real_sender_id': 2}))
                self.assertEqual([row['message_uid'] for row in app.auto_reply_candidate_messages(cfg, state, 10)], ['incoming'])
                cfg['reply_sender']['allowed_chats'] = []
                self.assertTrue(all(row['chat_username'].endswith('@chatroom') for row in app.auto_reply_candidate_messages(cfg, state, 10)))


if __name__ == '__main__':
    unittest.main()
