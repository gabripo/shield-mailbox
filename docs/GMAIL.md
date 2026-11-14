# Setting up the bot mailbox (Gmail)

One Gmail account receives the mail of all your bots. Your personal Gmail forwards only what the
bots need; inside the bot mailbox, filters put each bot's mail under its own label.

```
your Gmail ──(filter per source: forward)──► bot Gmail ──(filter per bot: label, skip Inbox)──► label = one bot
```

Any IMAP mailbox works; these steps use Gmail. They take about 15 minutes.

## 1. Create the bot Gmail and an app password

1. Sign out of Google (or use a private window) and create a new account at
   <https://accounts.google.com/signup>, e.g. `yourname.bots@gmail.com`. Use it **only** for the bots.
2. Turn on **2-Step Verification**: <https://myaccount.google.com/signinoptions/two-step-verification>.
3. Create an **app password** per bot: <https://myaccount.google.com/apppasswords> → name it after
   the bot (`jobbot`, `casabot`) → copy the 16 characters. An app password only opens the mail
   (IMAP); you can revoke one bot's access there without touching the others.
4. Store it in the bot's `.env` on the Shield the way the bot's README says (for bots deployed
   with a `deploy.sh`: `pbpaste | deploy/deploy.sh secret <NAME>`, then `pbcopy < /dev/null`), so
   it never appears on screen or in shell history.

## 2. One label per bot, inside the bot Gmail

In the **bot** Gmail (Settings → *Filters and Blocked Addresses* → *Create a new filter*):

| Bot | Filter | Actions |
|---|---|---|
| casabot | **From**: `immobiliare.it OR idealista.it OR idealista.com OR casa.it OR subito.it`<br>or **To**: `yourname.bots+casa@gmail.com` | **Skip the Inbox**, **Apply the label** `Casa` (new label), **Never send it to Spam** |
| jobbot | nothing: it reads the Inbox, where everything without a label stays | |

- **Skip the Inbox** keeps a bot's mail out of the Inbox, so a bot reading the Inbox (jobbot) never
  takes it. Each bot marks as read only the mail in its own label.
- **Plus-addresses**: mail to `yourname.bots+casa@gmail.com` lands in the same account; the *To*
  filter routes it. Give that address to people who should send things to one bot only.
- Gmail forwarding keeps the original sender, so a *From* filter here matches mail your personal
  Gmail forwards.

Check the labels from the Shield: `python3 -m shield_mailbox folders` (see the [README](../README.md#check-the-mailbox-from-the-shield)).

## 3. Forward from your personal Gmail

1. Personal Gmail → ⚙️ → **See all settings** → **Forwarding and POP/IMAP** → **Add a forwarding
   address** → the bot address → **Next** → **Proceed**.
2. Google sends a confirmation code **to the bot mailbox**: open it there (or see it with
   `python3 -m shield_mailbox test`) and click the link.
3. Leave **Disable forwarding** selected on that page: only the filters below forward.
4. One filter per source (search bar → filter icon):

   | For | From | Action |
   |---|---|---|
   | casabot | `immobiliare.it OR idealista.it OR idealista.com OR casa.it OR subito.it` | **Forward it to** the bot address |
   | jobbot | see jobbot's MAILBOX.md (LinkedIn, jobs.ch, …) | **Forward it to** the bot address |

   Don't tick *Skip the Inbox* here: you keep seeing these mails yourself. Gmail forwards only mail
   that arrives after the filter exists.

## 4. Test it end to end

1. From your personal Gmail, send a mail to `yourname.bots+casa@gmail.com` with a link in it.
2. On the Shield: `python3 -m shield_mailbox test --folder Casa …` shows it as unread (•).
3. The bot picks it up at its next mailbox check.

## Privacy

- Bots log into the **bot mailbox only**, over IMAP with TLS. They never send mail.
- Your personal mailbox shares only what the filters forward. To cut a bot off, delete its filter or
  revoke its app password.
- Mail stays in the bot mailbox until you delete it there.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Login failed … Invalid credentials` / `Application-specific password required` | Use an **app password** (step 1.3); 2-Step Verification must be on. |
| App passwords page says "not available" | 2-Step Verification is off, or the account is a managed (Workspace) account. Use a personal Gmail. |
| `Folder "Casa" not found` | Create the label (step 2); names are case-sensitive. `folders` lists them. |
| Nothing arrives in the label | The forwarding address isn't confirmed (3.2), or a filter doesn't match: open a real alert → ⋮ → *Filter messages like this* to see the exact sender. |
| A bot's mail shows up in another bot | The bot-Gmail filter is missing **Skip the Inbox**. |
