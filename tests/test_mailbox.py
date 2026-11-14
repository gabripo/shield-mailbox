"""Offline tests: a fake IMAP server stands in for Gmail.  python3 -m unittest discover tests"""
import imaplib
import unittest
from email.message import EmailMessage
from unittest import mock

from shield_mailbox import Mailbox, MailboxError, html_to_text, links_in


def make(subject, html=None, text=None, sender="Immobiliare.it <noreply@immobiliare.it>", to="mybots+casa@gmail.com",
         forwarded_from=None):
    m = EmailMessage()
    m["Subject"], m["From"], m["To"], m["Message-ID"] = subject, sender, to, f"<{abs(hash(subject))}@test>"
    if forwarded_from:
        m["X-Forwarded-For"] = f"{forwarded_from} mybots@gmail.com"
    if text:
        m.set_content(text)
    if html:
        if text:
            m.add_alternative(html, subtype="html")
        else:
            m.set_content(html, subtype="html")
    return m.as_bytes()


class FakeIMAP:
    """Just enough IMAP4 for Mailbox: folders hold [uid, raw, seen]."""
    boxes = {}
    password = "app-password"

    def __init__(self, host, port=993, timeout=None):
        self.box = None
        self.readonly = False

    def login(self, user, password):
        if password != self.password:
            raise imaplib.IMAP4.error("[AUTHENTICATIONFAILED] Invalid credentials")

    def select(self, folder, readonly=False):
        name = folder.strip('"')
        if name not in self.boxes:
            return "NO", [b"[NONEXISTENT] Unknown Mailbox"]
        self.box, self.readonly = self.boxes[name], readonly
        return "OK", [str(len(self.box)).encode()]

    def uid(self, command, *args):
        if command == "search":
            crit = args[-1]
            uids = [str(u).encode() for u, _, seen in self.box if crit == "ALL" or not seen]
            return "OK", [b" ".join(uids)]
        uid = int(args[0])
        row = next(r for r in self.box if r[0] == uid)
        if command == "fetch":
            return "OK", [(f"{uid} (UID {uid} BODY[] {{{len(row[1])}}}".encode(), row[1]), b")"]
        if command == "store":
            assert not self.readonly, "store on a read-only select"
            row[2] = True
            return "OK", [b""]
        raise AssertionError(command)

    def list(self):
        return "OK", [b'(\\HasNoChildren) "/" "INBOX"', b'(\\HasNoChildren) "/" "Casa"',
                      b'(\\Noselect \\HasChildren) "/" "[Gmail]"', b'(\\HasNoChildren) "/" "Bots/Jobs"']

    def logout(self):
        pass


ALERT_HTML = """<html><head><style>p{color:red}</style></head><body>
<h1>3 nuovi annunci per "Camigliatello"</h1>
<table><tr><td><a href="https://www.immobiliare.it/annunci/134530643/?utm_source=alert&amp;x=1">Trilocale via della Repubblica 93</a></td>
<td>&euro; 79.000 &middot; 79&nbsp;m²</td></tr></table>
<script>track()</script></body></html>"""


class MailboxTest(unittest.TestCase):
    def setUp(self):
        FakeIMAP.boxes = {
            "INBOX": [[1, make("Job alert", text="New jobs for you"), False]],
            "Casa": [[7, make("Nuovi annunci", html=ALERT_HTML), True],
                     [8, make("Nuovi annunci 2", html=ALERT_HTML, text="Vedi https://www.idealista.it/immobile/12345678/."), False],
                     [9, make("Fwd: proposta", text="---------- Forwarded message ---------\nFrom: Maria <maria@example.com>\nhttps://www.casa.it/immobili/123/",
                              sender="Me <me@gmail.com>"), False]],
        }
        p = mock.patch.object(imaplib, "IMAP4_SSL", FakeIMAP)
        p.start()
        self.addCleanup(p.stop)

    def test_reads_only_its_folder_and_marks_read_after_handling(self):
        mb = Mailbox("imap.gmail.com", "mybots@gmail.com", "app-password", folder="Casa")
        got = []
        for mail in mb.iter_new():
            self.assertFalse(next(r for r in FakeIMAP.boxes["Casa"] if r[0] == int(mail.uid))[2], "read before handled")
            got.append(mail)
        self.assertEqual([m.subject for m in got], ["Nuovi annunci 2", "Fwd: proposta"])
        self.assertTrue(all(r[2] for r in FakeIMAP.boxes["Casa"]))
        self.assertFalse(FakeIMAP.boxes["INBOX"][0][2], "another bot's folder was touched")
        self.assertEqual(mb.fetch_new(), [])

    def test_crash_leaves_mail_unread(self):
        mb = Mailbox("imap.gmail.com", "mybots@gmail.com", "app-password", folder="Casa")
        with self.assertRaises(RuntimeError):
            for _ in mb.iter_new():
                raise RuntimeError("boom")
        self.assertFalse(FakeIMAP.boxes["Casa"][1][2])

    def test_fields(self):
        mail, forwarded = Mailbox("h", "u", "app-password", folder="Casa").fetch_new()
        self.assertEqual(mail.to, "mybots+casa@gmail.com")
        self.assertEqual(mail.sender, "noreply@immobiliare.it")
        self.assertIn("https://www.immobiliare.it/annunci/134530643/?utm_source=alert&x=1", [u for u, _ in mail.links])
        self.assertIn("https://www.idealista.it/immobile/12345678/", [u for u, _ in mail.links])
        self.assertIn("Trilocale via della Repubblica 93", dict(mail.links).values())
        self.assertEqual(forwarded.sender, "maria@example.com")

    def test_peek_changes_nothing(self):
        rows = Mailbox("h", "u", "app-password", folder="Casa").peek(10)
        self.assertEqual([(m.uid, new) for m, new in rows], [("7", False), ("8", True), ("9", True)])
        self.assertEqual([r[2] for r in FakeIMAP.boxes["Casa"]], [True, False, False])

    def test_errors_say_what_to_check(self):
        with self.assertRaisesRegex(MailboxError, "app password"):
            Mailbox("h", "u", "wrong", folder="Casa").peek()
        with self.assertRaisesRegex(MailboxError, 'Folder "Nope" not found'):
            Mailbox("h", "u", "app-password", folder="Nope").peek()
        with self.assertRaises(MailboxError):
            Mailbox("h", "u", "")

    def test_folders(self):
        self.assertEqual(Mailbox("h", "u", "app-password").folders(), ["INBOX", "Casa", "Bots/Jobs"])


class HtmlTest(unittest.TestCase):
    def test_text(self):
        t = html_to_text(ALERT_HTML)
        self.assertIn("Trilocale via della Repubblica 93", t)
        self.assertIn("€ 79.000 · 79 m²", t)
        self.assertNotIn("track()", t)
        self.assertNotIn("color", t)

    def test_links(self):
        self.assertEqual(links_in("", "see https://a.it/x, and https://a.it/x."), [("https://a.it/x", "")])
        self.assertEqual(links_in('<a href="mailto:x@y.z">m</a><a href="https://b.it">B</a>'), [("https://b.it", "B")])


if __name__ == "__main__":
    unittest.main()
