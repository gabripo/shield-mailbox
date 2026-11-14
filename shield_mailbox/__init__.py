"""shield-mailbox: one bot mailbox shared by the bots on an NVIDIA Shield (standard library only).

    from shield_mailbox import Mailbox
    for mail in Mailbox("imap.gmail.com", user, app_password, folder="Casa").iter_new():
        print(mail.sender, mail.subject, mail.links)
"""
from .mailbox import Mail, Mailbox, MailboxError, html_to_text, links_in, original_sender

__all__ = ["Mail", "Mailbox", "MailboxError", "html_to_text", "links_in", "original_sender"]
__version__ = "0.1.0"
