# shield-mailbox

**One bot mailbox for all the bots on your NVIDIA Shield.** Your personal Gmail forwards only the
emails a bot needs (job alerts, house alerts, …) to a separate **bot Gmail**; inside it, a label per
bot keeps each bot's mail apart. Each bot reads **only its own label** over IMAP, with an app
password, and never logs into your personal inbox.

```
 LinkedIn / jobs.ch alerts ─┐                         ┌─ Inbox ──► jobbot
 immobiliare / idealista  ──┼─► your Gmail ─(filters)─►  bot Gmail ─┤
 friends' proposals ────────┘   you still see          └─ label "Casa" ──► casabot
   (mybots+casa@gmail.com)      everything as usual        (one label per bot)
```

- **Standard library only** (Python 3.8+): nothing to install on the Shield, ~250 lines.
- **Safe to share**: a bot only reads and marks as read the mail in its own label; a mail is marked
  read only after the bot handled it, so a crash leaves it for the next run.
- **Gives a bot what it needs**: subject, original sender (also for forwarded mail), the address it
  was sent to (plus-addresses like `mybots+casa@gmail.com`), plain text, HTML as text, and every link.
- **Read-only checks** from the command line: log in, list folders, show the last mails.

Made for the bots built on **[nvidia-shield-sword](https://github.com/gabripo/nvidia-shield-sword)**
(Termux + Debian on the Shield), but it works anywhere Python runs.

## Set up the bot mailbox

**[docs/GMAIL.md](docs/GMAIL.md)**: create the bot Gmail and an app password, forward from your
personal Gmail with filters, and give each bot its label.

## Use it in a bot

```python
from shield_mailbox import Mailbox

box = Mailbox("imap.gmail.com", "mybots@gmail.com", app_password, folder="Casa")
for mail in box.iter_new(limit=50):           # unread mail in the label, oldest first
    print(mail.sender, mail.to, mail.subject)
    for url, anchor in mail.links:            # every link of the HTML and of the text
        ...
    text = mail.body                          # plain text, or the HTML turned into text
# each mail is marked read after its loop body finished
```

| API | |
|---|---|
| `Mailbox(host, user, password, folder="INBOX")` | One folder of the mailbox; with Gmail a folder is a label (`"Casa"`, `"Bots/Casa"`) |
| `.iter_new(limit=50, mark_seen=True)` | Unread mail, oldest first, marked read after you handled it |
| `.fetch_new(limit=50, mark_seen=True)` | The same as a list (marked read as soon as fetched) |
| `.peek(limit=10)` | The last mails with an unread flag, changing nothing |
| `.folders()` | The folder (label) names |
| `Mail` | `uid, message_id, received, sender, to, subject, text, html, folder`, plus `.body`, `.links`, `.as_dict()` |
| `html_to_text(html)`, `links_in(html, text)` | The helpers behind `.body` and `.links` |
| `MailboxError` | Login or folder problems, with a message that says what to check |

### Add it to a bot repository

As a git submodule, so each bot pins the version it was tested with:

```bash
git submodule add https://github.com/gabripo/shield-mailbox lib/shield-mailbox
```

Then, before importing (the bot stays standard-library only, no pip):

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib" / "shield-mailbox"))
from shield_mailbox import Mailbox
```

Copy `lib/shield-mailbox/shield_mailbox/` to the Shield with the rest of the bot (a `tar` of the
working tree includes it). After cloning a bot repository: `git submodule update --init`.

## Check the mailbox from the Shield

```bash
cd lib/shield-mailbox
python3 -m shield_mailbox folders --env /root/mybot/.env --password-env MYBOT_IMAP_PASSWORD --user mybots@gmail.com
python3 -m shield_mailbox test --folder Casa --env /root/mybot/.env --password-env MYBOT_IMAP_PASSWORD --user mybots@gmail.com
```

Both are read-only. Settings may also come from `SHIELD_MAILBOX_HOST` (default `imap.gmail.com`),
`SHIELD_MAILBOX_USER` and `SHIELD_MAILBOX_PASSWORD`.

## Tests

```bash
python3 -m unittest discover -s tests
```

They run offline against a fake IMAP server.

## Used by

- **jobbot**: job alerts and recruiter mail (Inbox).
- **casa-sila**: house-ad alerts from immobiliare.it, idealista, casa.it and subito.it, plus ads
  proposed by friends (label `Casa`).

## License

MIT, see [LICENSE](LICENSE).
