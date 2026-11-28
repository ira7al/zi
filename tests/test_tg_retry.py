"""Telegram calls survive a network blip instead of losing the message."""
import io, json, os, sys, unittest, urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb  # noqa: E402


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def ok(body):
    return FakeResp(json.dumps(body).encode())


class RetryTests(unittest.TestCase):
    def setUp(self):
        self.tg = zb.TG("T")
        self.sleeps = []
        patcher = mock.patch.object(zb.time, "sleep", lambda s: self.sleeps.append(s))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_one_timeout_then_success(self):
        seq = [urllib.error.URLError("timed out"), ok({"ok": True, "result": {"message_id": 5}})]
        with mock.patch.object(zb.urllib.request, "urlopen", side_effect=seq):
            self.assertEqual(self.tg.call("sendMessage", chat_id=1, text="hi"), {"message_id": 5})
        self.assertEqual(len(self.sleeps), 1)

    def test_429_waits_the_retry_after_and_then_sends(self):
        seq = [ok({"ok": False, "error_code": 429, "description": "Too Many Requests: retry after 4",
                   "parameters": {"retry_after": 4}}),
               ok({"ok": True, "result": True})]
        with mock.patch.object(zb.urllib.request, "urlopen", side_effect=seq):
            self.assertTrue(self.tg.call("sendMessage", chat_id=1, text="hi"))
        self.assertEqual(self.sleeps, [4])

    def test_a_bad_request_is_not_retried(self):
        body = io.BytesIO(b'{"ok": false, "error_code": 400, "description": "Bad Request: chat not found"}')
        err = urllib.error.HTTPError("u", 400, "Bad Request", {}, body)
        with mock.patch.object(zb.urllib.request, "urlopen", side_effect=[err]):
            with self.assertRaises(RuntimeError) as ctx:
                self.tg.call("sendMessage", chat_id=1, text="hi")
        self.assertIn("chat not found", str(ctx.exception))
        self.assertEqual(self.sleeps, [])

    def test_gives_up_after_three_tries(self):
        with mock.patch.object(zb.urllib.request, "urlopen",
                               side_effect=urllib.error.URLError("no route to host")):
            with self.assertRaises(urllib.error.URLError):
                self.tg.call("sendMessage", chat_id=1, text="hi")
        self.assertEqual(len(self.sleeps), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
