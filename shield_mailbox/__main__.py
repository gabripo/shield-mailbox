"""Command line: check the bot mailbox from the Shield (read-only).

    python3 -m shield_mailbox test    [--folder Casa] [--limit 10]
    python3 -m shield_mailbox folders

Settings come from the environment (or an .env file given with --env):
    SHIELD_MAILBOX_HOST      default imap.gmail.com
    SHIELD_MAILBOX_USER      the bot mailbox address
    SHIELD_MAILBOX_PASSWORD  its app password (or name another variable with --password-env)
"""
import argparse
import os
import sys

from . import Mailbox, MailboxError


def load_env(path):
    values = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m shield_mailbox", description="Check the shared bot mailbox (read-only).")
    ap.add_argument("command", choices=["test", "folders"])
    ap.add_argument("--env", help="KEY=VALUE file with the settings, e.g. /root/jobbot/.env")
    ap.add_argument("--host")
    ap.add_argument("--user")
    ap.add_argument("--password-env", default="SHIELD_MAILBOX_PASSWORD", help="variable that holds the app password")
    ap.add_argument("--folder", default="INBOX", help='folder or Gmail label, e.g. INBOX, Casa, "Bots/Casa"')
    ap.add_argument("--limit", type=int, default=10)
    a = ap.parse_args(argv)

    env = dict(os.environ)
    if a.env:
        env.update(load_env(a.env))
    host = a.host or env.get("SHIELD_MAILBOX_HOST") or "imap.gmail.com"
    user = a.user or env.get("SHIELD_MAILBOX_USER")
    password = env.get(a.password_env)
    if not user or not password:
        print(f"Missing settings: SHIELD_MAILBOX_USER (or --user) and {a.password_env}.", file=sys.stderr)
        return 2
    try:
        if a.command == "folders":
            for name in Mailbox(host, user, password).folders():
                print(name)
            return 0
        rows = Mailbox(host, user, password, folder=a.folder).peek(a.limit)
        unread = sum(1 for _, new in rows if new)
        print(f"Logged in as {user}: folder {a.folder}, last {len(rows)} mails, {unread} unread (nothing was changed).")
        for mail, new in rows:
            print(f"  {'•' if new else ' '} {mail.sender[:38]:38} {mail.subject[:70]}")
        return 0
    except MailboxError as e:
        print(e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
