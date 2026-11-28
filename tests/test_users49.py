import base64, json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import zi_bot as zb
from bot import zi_options as zo
from tests.test_voice import FakeTG


class Resp:
    def __init__(self, d): self.d = d
    def read(self): return json.dumps(self.d).encode()
    def __enter__(self): return self
    def __exit__(self, *a): return False


def make(owner=7835590874):
    t = tempfile.mkdtemp()
    b = zb.Bot("T", out_root=t, work=t, make_track=lambda s: None)
    b.tg = FakeTG(); b._launcher_sent = True
    b.owner = owner
    return b


class Users(unittest.TestCase):
    def test_note_user(self):
        users = {}
        p = zo.user_from_update({"id": 5, "first_name": "A", "last_name": "B", "username": "ab"})
        self.assertEqual(zo.note_user(users, p, "t1"), (True, True))
        self.assertEqual(users["5"]["name"], "A B")
        self.assertEqual((users["5"]["plan"], users["5"]["role"]), ("free", "user"))
        o = {}
        zo.note_user(o, zo.user_from_update({"id": 1}), "t", True)
        self.assertEqual((o["1"]["plan"], o["1"]["role"]), ("owner", "admin"))
        self.assertEqual(zo.note_user(users, p, "t2"), (False, False))
        self.assertEqual(users["5"]["first_seen"], "t1")
        self.assertIsNone(zo.user_from_update({}))

    def test_clean_track_drops_unlisted_fields(self):
        out = zo.clean_track({"title": "T", "token": "SECRET", "folder": "/x"}, {"id": "k"})
        self.assertEqual(out, {"title": "T", "id": "k"})

    def test_github_put_never_sends_token_in_body_and_skips_unchanged(self):
        calls = []
        def op(req, timeout=0):
            calls.append((req.get_method(), req.full_url, req.data))
            if req.get_method() == "GET":
                import urllib.error
                raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, None)
            return Resp({})
        hashes = {}
        pushed, probs = zo.sync_private("o/r", "TOK", {"users/1.json": "{}"}, hashes, opener=op)
        self.assertEqual((pushed, probs), (["users/1.json"], []))
        body = json.loads(calls[-1][2])
        self.assertEqual(base64.b64decode(body["content"]), b"{}")
        self.assertNotIn("TOK", json.dumps(body))
        n = len(calls)
        zo.sync_private("o/r", "TOK", {"users/1.json": "{}"}, hashes, opener=op)
        self.assertEqual(len(calls), n)
        self.assertEqual(zo.sync_private("o/r", "", {"a": "b"}, {})[1], ["no repo or token"])

    def test_stranger_gets_notice_once_and_is_recorded(self):
        b = make()
        u = {"update_id": 1, "message": {"chat": {"id": 99}, "from": {"id": 99, "first_name": "Sam"}, "text": "hi"}}
        b._handle(u); b._handle(u)
        msgs = [str(m) for m in b.tg.sent]
        self.assertEqual(sum(zo.USERS_NOTICE in m for m in msgs), 1)
        self.assertIn("99", b.users)
        self.assertFalse(b.users["99"]["is_owner"])

    def test_owner_is_known_without_pairing(self):
        t = tempfile.mkdtemp()
        b = zb.Bot("T", out_root=t, work=t, make_track=lambda s: None)
        self.assertEqual(b.owner, 7835590874)
        self.assertTrue(b._is_owner(7835590874))
        self.assertEqual(json.load(open(os.path.join(t, "zi_bot_owner.json")))["chat_id"], 7835590874)
        os.environ["ZI_OWNER_ID"] = "5"
        try:
            t2 = tempfile.mkdtemp()
            self.assertEqual(zb.Bot("T", out_root=t2, work=t2, make_track=lambda s: None).owner, 5)
        finally:
            del os.environ["ZI_OWNER_ID"]
        json.dump({"chat_id": 42}, open(os.path.join(t, "zi_bot_owner.json"), "w"))
        self.assertEqual(zb.Bot("T", out_root=t, work=t, make_track=lambda s: None).owner, 42)

    def test_sync_files_have_profile_and_library_only(self):
        b = make()
        b._track_user({"id": 7835590874, "first_name": "R"})
        f = b._sync_files()
        self.assertIn("users/7835590874.json", f)
        self.assertIn("library/7835590874.json", f)
        self.assertTrue(json.loads(f["users/7835590874.json"])["is_owner"])
        b.sync_status = ""
        self.assertFalse(b._sync_once())          # no token: local only, no crash
        self.assertIn("device only", b.sync_status)


class Phone(unittest.TestCase):
    def test_contact_must_be_own(self):
        users = {}
        zo.note_user(users, zo.user_from_update({"id": 5}), "t")
        self.assertEqual(zo.accept_contact(users, {"id": 5}, {"user_id": 6, "phone_number": "20100"}, "n"), (False, "not own number"))
        self.assertEqual(zo.accept_contact(users, {"id": 5}, {"phone_number": "201001234567"}, "n"), (False, "not own number"))
        self.assertNotIn("phone", users["5"])
        ok, ph = zo.accept_contact(users, {"id": 5}, {"user_id": 5, "phone_number": "201001234567"}, "n")
        self.assertEqual((ok, ph), (True, "+201001234567"))
        self.assertTrue(users["5"]["phone_verified"])
        self.assertIn("phone_verified", zo.clean_profile(users["5"]))

    def test_bot_flow(self):
        b = make()
        hi = {"update_id": 1, "message": {"chat": {"id": 99}, "from": {"id": 99, "first_name": "S"}, "text": "hi"}}
        seen = []
        orig = b.tg.send
        b.tg.send = lambda c, text, keyboard=None, reply=None: (seen.append(reply), orig(c, text, keyboard))[1]
        b._handle(hi)
        self.assertTrue(any("request_contact" in json.dumps(r) for r in seen if r))
        fake = {"update_id": 2, "message": {"chat": {"id": 99}, "from": {"id": 99}, "contact": {"user_id": 123, "phone_number": "1555"}}}
        b._handle(fake)
        self.assertFalse(b.users["99"].get("phone_verified"))
        good = {"update_id": 3, "message": {"chat": {"id": 99}, "from": {"id": 99}, "contact": {"user_id": 99, "phone_number": "201001234567"}}}
        b._handle(good)
        self.assertTrue(b.users["99"]["phone_verified"])
        self.assertEqual(zo.PHONE_PROOF["sms"], None)
