from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from league.lcu_client import Credentials, LcuClient


class LcuClientTest(unittest.TestCase):
    @patch("urllib.request.Request")
    def test_normalizes_leading_slash_in_path(self, mock_request):
        creds = Credentials(port=1234, token="secret")
        client = LcuClient(creds)
        client._opener = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"{}"
        client._opener.open.return_value.__enter__.return_value = mock_resp

        client.raw_request("GET", "lol-summoner/v1/current-summoner")
        mock_request.assert_called_once()
        url = mock_request.call_args[0][0]
        self.assertEqual(url, "https://127.0.0.1:1234/lol-summoner/v1/current-summoner")

    @patch("urllib.request.Request")
    def test_preserves_existing_leading_slash(self, mock_request):
        creds = Credentials(port=1234, token="secret")
        client = LcuClient(creds)
        client._opener = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"{}"
        client._opener.open.return_value.__enter__.return_value = mock_resp

        client.raw_request("GET", "/lol-summoner/v1/current-summoner")
        mock_request.assert_called_once()
        url = mock_request.call_args[0][0]
        self.assertEqual(url, "https://127.0.0.1:1234/lol-summoner/v1/current-summoner")


if __name__ == "__main__":
    unittest.main()
