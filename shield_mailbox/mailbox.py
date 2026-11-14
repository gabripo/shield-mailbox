"""Read one folder (a Gmail label) of the shared bot mailbox over IMAP. Standard library only."""
import email
import email.header
import email.utils
import html as htmllib
import imaplib
import re
from dataclasses import dataclass
from html.parser import HTMLParser

__all__ = ["Mailbox", "Mail", "MailboxError", "html_to_text", "links_in", "original_sender"]


class MailboxError(Exception):
    """Login or folder problem, with a message that says what to check."""


# --- message parts -----------------------------------------------------------

def decode_header(value):
    parts = email.header.decode_header(value or "")
    return "".join(p.decode(enc or "utf-8", "replace") if isinstance(p, bytes) else p for p, enc in parts)


def _bodies(msg):
    """First text/plain and first text/html part (attachments skipped)."""
    text, html = "", ""
    for part in msg.walk():
        if part.get_content_maintype() == "multipart" or str(part.get("Content-Disposition", "")).startswith("attachment"):
            continue
        payload = part.get_payload(decode=True) or b""
        charset = part.get_content_charset() or "utf-8"
        try:
            decoded = payload.decode(charset, "replace")
        except LookupError:
            decoded = payload.decode("utf-8", "replace")
        if part.get_content_type() == "text/plain" and not text:
            text = decoded
        elif part.get_content_type() == "text/html" and not html:
            html = decoded
    return text, html


def original_sender(msg, text=""):
    """For mail forwarded by a filter the real sender is in the forwarded header block or X-Forwarded-For."""
    m = re.search(r"^\s*(?:From|Da|De|Von):\s*.*?<?([\w.+-]+@[\w.-]+)>?", text or "", re.M)
    fwd = msg.get("X-Forwarded-For", "")
    return m.group(1) if m else (fwd.split()[0] if fwd else email.utils.parseaddr(msg.get("From", ""))[1])


# --- HTML helpers --------------------------------------------------------------

_BLOCK = {"p", "div", "br", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section",
          "article", "ul", "ol", "header", "footer", "dd", "dt", "blockquote", "pre", "hr"}
_SKIP = {"script", "style", "noscript", "template", "head", "title"}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.links, self.href, self.anchor = [], 0, [], None, []

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self.skip += 1
        if tag in _BLOCK:
            self.out.append("\n")
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.anchor = []

    def handle_endtag(self, tag):
        if tag in _SKIP and self.skip:
            self.skip -= 1
        if tag in _BLOCK:
            self.out.append("\n")
        if tag == "a" and self.href:
            self.links.append((self.href.strip(), " ".join("".join(self.anchor).split())))
            self.href = None

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)
            if self.href is not None:
                self.anchor.append(data)


def html_to_text(html):
    """Readable text from HTML: one line per block, no scripts or styles."""
    p = _Text()
    p.feed(html or "")
    p.close()
    lines = [" ".join(line.split()) for line in "".join(p.out).replace("\xa0", " ").split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


_URL = re.compile(r"https?://[^\s<>\"')\]]+")


def links_in(html="", text=""):
    """[(url, anchor text)] from the HTML links and the bare URLs of the text, in order, without duplicates."""
    found = []
    if html:
        p = _Text()
        p.feed(html)
        p.close()
        found += [(htmllib.unescape(u), a) for u, a in p.links if u.lower().startswith(("http://", "https://"))]
    found += [(u.rstrip(".,;:"), "") for u in _URL.findall(text or "")]
    seen, out = set(), []
    for url, anchor in found:
        if url not in seen:
            seen.add(url)
            out.append((url, anchor))
    return out


# --- the mailbox -----------------------------------------------------------------

@dataclass
class Mail:
    uid: str
    message_id: str
    received: str
    sender: str      # the original sender, also for mail forwarded by a filter
    to: str          # the address it was sent to, e.g. a plus-address like mybots+casa@gmail.com
    subject: str
    text: str        # the text/plain part ('' if the mail has only HTML)
    html: str
    folder: str

    @property
    def body(self):
        """The text to read: the plain part, else the HTML turned into text."""
        return self.text.strip() or html_to_text(self.html)

    @property
    def links(self):
        return links_in(self.html, self.text)

    def as_dict(self):
        return {"id": self.message_id, "uid": self.uid, "received": self.received, "sender": self.sender, "to": self.to,
                "subject": self.subject, "text": self.text, "html": self.html, "folder": self.folder}


def _quote(folder):
    return folder if folder.startswith('"') else '"' + folder.replace("\\", "\\\\").replace('"', '\\"') + '"'


class Mailbox:
    """One folder of the bot mailbox. With Gmail a folder is a label: "INBOX", "Casa", "Bots/Casa"…

    Each bot reads its own label, so several bots share one mailbox without taking each other's mail.
    """

    def __init__(self, host, user, password, folder="INBOX", port=993, timeout=60):
        if not (host and user and password):
            raise MailboxError("mailbox not configured: host, user and app password are needed")
        self.host, self.user, self.password, self.folder, self.port, self.timeout = host, user, password, folder, port, timeout

    def _connect(self, readonly):
        try:
            imap = imaplib.IMAP4_SSL(self.host, self.port, timeout=self.timeout)
        except TypeError:  # Python < 3.9 has no timeout argument
            imap = imaplib.IMAP4_SSL(self.host, self.port)
        try:
            imap.login(self.user, self.password)
        except imaplib.IMAP4.error as e:
            raise MailboxError(f"Login failed for {self.user}: {e}. Use an app password (2-Step Verification on).") from None
        status, data = imap.select(_quote(self.folder), readonly=readonly)
        if status != "OK":
            try:
                imap.logout()
            finally:
                raise MailboxError(f'Folder "{self.folder}" not found in {self.user}: create the label, or check its name '
                                   f'with: python3 -m shield_mailbox folders')
        return imap

    def _mail(self, imap, uid):
        status, data = imap.uid("fetch", uid, "(BODY.PEEK[])")
        raw = next((part[1] for part in data or [] if isinstance(part, tuple)), None)
        if status != "OK" or raw is None:
            return None
        msg = email.message_from_bytes(raw)
        text, html = _bodies(msg)
        return Mail(
            uid=uid.decode() if isinstance(uid, bytes) else str(uid),
            message_id=(msg.get("Message-ID") or "").strip() or f"{self.user}:{self.folder}:{uid}",
            received=msg.get("Date", ""),
            sender=original_sender(msg, text or html_to_text(html)[:3000]),
            to=email.utils.parseaddr(msg.get("Delivered-To") or msg.get("To", ""))[1],
            subject=decode_header(msg.get("Subject")),
            text=text, html=html, folder=self.folder,
        )

    def iter_new(self, limit=50, mark_seen=True):
        """Unread mail, oldest first. Each mail is marked read only after the loop body that handled it
        finished, so a crash leaves it unread for the next run."""
        imap = self._connect(readonly=not mark_seen)
        try:
            status, data = imap.uid("search", None, "UNSEEN")
            uids = (data[0].split() if status == "OK" and data and data[0] else [])[-limit:]
            for uid in uids:
                mail = self._mail(imap, uid)
                if mail is None:
                    continue
                yield mail
                if mark_seen:
                    imap.uid("store", uid, "+FLAGS", "(\\Seen)")
        finally:
            try:
                imap.logout()
            except Exception:  # noqa: BLE001 - the connection may already be gone
                pass

    def fetch_new(self, limit=50, mark_seen=True):
        """Like iter_new, as a list: every mail is marked read as soon as it is fetched."""
        return list(self.iter_new(limit=limit, mark_seen=mark_seen))

    def peek(self, limit=10):
        """The last `limit` mails of the folder, read or not, without changing anything."""
        imap = self._connect(readonly=True)
        try:
            status, data = imap.uid("search", None, "ALL")
            uids = (data[0].split() if status == "OK" and data and data[0] else [])[-limit:]
            unseen = set()
            status, data = imap.uid("search", None, "UNSEEN")
            if status == "OK" and data and data[0]:
                unseen = set(data[0].split())
            out = []
            for uid in uids:
                mail = self._mail(imap, uid)
                if mail:
                    out.append((mail, uid in unseen))
            return out
        finally:
            try:
                imap.logout()
            except Exception:  # noqa: BLE001
                pass

    def folders(self):
        """Folder (label) names of the mailbox."""
        try:
            imap = imaplib.IMAP4_SSL(self.host, self.port)
            imap.login(self.user, self.password)
        except imaplib.IMAP4.error as e:
            raise MailboxError(f"Login failed for {self.user}: {e}") from None
        try:
            status, data = imap.list()
            names = []
            for line in data or []:
                line = line.decode() if isinstance(line, bytes) else str(line)
                m = re.match(r'\((?P<flags>[^)]*)\) (?P<sep>"[^"]*"|NIL) (?P<name>.+)$', line)
                if m and "\\Noselect" not in m.group("flags"):
                    name = m.group("name").strip()
                    names.append(name[1:-1].replace('\\"', '"') if name.startswith('"') else name)
            return names
        finally:
            try:
                imap.logout()
            except Exception:  # noqa: BLE001
                pass
