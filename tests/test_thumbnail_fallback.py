import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from memory.media_sync import sync_image


class ThumbnailFallbackTest(unittest.TestCase):
    def test_uses_valid_thumbnail_when_original_is_wxgf(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            high, thumb = root / 'a_h.dat', root / 'a_t.dat'
            row = {'chat_username': 'c', 'local_id': 1, 'message_uid': 'm'}
            args = SimpleNamespace(wechat_base_dir=root, prefer_thumbnails=False, media_dir=root)

            def decode(path, *_):
                return (b'wxgfDATA', 'hevc') if path == high else (b'\xff\xd8\xfftest\xff\xd9', 'jpg')

            with patch('memory.media_sync.find_dat_files', return_value=[high, thumb]), \
                 patch('memory.media_sync.decrypt_dat', side_effect=decode), \
                 patch('memory.media_sync.image_dimensions', return_value=(1, 1)):
                result = sync_image(row, args, {('c', 1): 'hash'}, {})
            self.assertEqual(result['status'], 'ready')
            self.assertEqual(result['source_path'], str(thumb))


if __name__ == '__main__':
    unittest.main()
