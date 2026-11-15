# Phone capture setup

The working hosted flow uses **iPhone Shortcuts → dictation or typed input → authenticated HTTPS capture**. Between receives text, not microphone audio. Use the existing authorized Shortcut for the live application; preserve its working token.

## Hosted Shortcut

The private Shortcut URL is obtained through `deploy/hosted-link.sh shortcut` by an authorized operator after confirming the host's persisted token exists. That helper copies the URL to the clipboard; do not expose the URL action, clipboard, or token in screenshots or recordings. The helper has a known fresh-host validation limitation described in [DEPLOY.md](DEPLOY.md).

For a dictation Shortcut:

1. Add **Dictate Text**.
2. Add **Get Contents of URL** with the authorized HTTPS capture URL.
3. Set **Method** to **POST** and **Request Body** to **JSON**.
4. Add `text` using the **Dictated Text** variable, and `source` with the value `phone`.
5. Set **Content-Type** to **application/json**; remove empty header rows.
6. Confirm the result appears in the authenticated dashboard. A local notification alone does not prove delivery.

For typing, replace Dictate Text with **Ask for Input** and use its Provided Input variable. A Type/Dictate menu needs the correct URL and JSON in both branches.

A keyless repeated capture has a bounded ten-minute retry receipt. The dashboard supplies an explicit retry key. These mechanisms reduce accidental duplicate submission; conservative task matching is a separate check.

## Independent local development

Use a clean checkout without production credentials or data. Both devices must share a network that permits device-to-device traffic. In that isolated checkout:

```bash
scripts/start-phone.sh
/usr/bin/python3 scripts/phone_link.py
```

The first command runs the local development server on the network. The second copies its current private capture URL. Its host uses the Mac's discovered Bonjour name. Use `--ip` only if local name resolution fails.

Do not use `--new-token` merely to copy a link: it rotates authentication and invalidates existing links. A wrong token requires checking the intended environment and saved link before deciding whether rotation is appropriate.

## Troubleshooting

- **Phone token required:** verify the saved link belongs to the intended host and still carries its valid token.
- **Empty capture:** check that `text` points to the selected branch's input variable rather than an empty literal.
- **Local timeout:** confirm the isolated server is running, the Mac is awake, and the network permits local connections.
- **Delayed display:** refresh the dashboard; cross-device changes are polled rather than pushed.

Phone tests create real captures in whichever environment the URL targets. Use intentional demo text, and do not delete existing data as part of setup.
