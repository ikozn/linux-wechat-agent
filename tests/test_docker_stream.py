import importlib.util
import socket
import sys
import threading
import time
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / 'ai'), str(root / 'web'), str(root / 'status')]
spec = importlib.util.spec_from_file_location('agent_app', root / 'agent_console/app.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class DockerStreamTest(unittest.TestCase):
    def test_waits_for_stream_after_headers(self):
        reader, writer = socket.socketpair()
        def respond():
            writer.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: application/vnd.docker.raw-stream\r\n\r\n')
            time.sleep(0.05)
            writer.sendall(b'payload')
            writer.close()
        thread = threading.Thread(target=respond)
        thread.start()
        try:
            status, _, body = app.read_http_response(reader, 2)
            self.assertEqual((status, body), (200, b'payload'))
        finally:
            reader.close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
