import unittest
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from serial_bridge import MAX_WORD, parse_word, send_word


class ParseWordTests(unittest.TestCase):
    def test_parses_decimal_hex_and_binary(self):
        self.assertEqual(parse_word("4294967295\r\n"), MAX_WORD)
        self.assertEqual(parse_word("0xFFFFFFFF"), MAX_WORD)
        self.assertEqual(parse_word("0b" + "1" * 32), MAX_WORD)
        self.assertEqual(parse_word("0" * 31 + "1"), 1)

    def test_rejects_empty_invalid_and_out_of_range_values(self):
        for value in ("", "not-a-word", "4294967296", "-1", "0xGG"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_word(value)


class SendWordTests(unittest.TestCase):
    def test_posts_word_to_api(self):
        received = {}

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                received["path"] = self.path
                received["headers"] = self.headers
                received["payload"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                body = json.dumps({"id": 7}).encode()
                self.send_response(201)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            result = send_word(f"http://127.0.0.1:{server.server_port}", 0x80000000, "ARD-1")
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

        self.assertEqual(result, {"id": 7})
        self.assertEqual(received["path"], "/api/envios")
        self.assertEqual(received["payload"]["dato_raw"], 0x80000000)
        self.assertEqual(received["payload"]["numero_serie"], "ARD-1")
        self.assertEqual(received["payload"]["tipo_instrumento"], "digital")
        self.assertTrue(received["headers"].get("Idempotency-Key"))


if __name__ == "__main__":
    unittest.main()