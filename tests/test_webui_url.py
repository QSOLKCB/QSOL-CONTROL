import unittest

from webui.http import webui_url


class WebUIUrlTests(unittest.TestCase):
    def test_ipv6_loopback_url_is_bracketed(self):
        self.assertEqual(webui_url("::1", 8765), "http://[::1]:8765")
        self.assertEqual(webui_url("127.0.0.1", 8765), "http://127.0.0.1:8765")
        self.assertEqual(webui_url("localhost", 8765), "http://localhost:8765")


if __name__ == "__main__":
    unittest.main()
