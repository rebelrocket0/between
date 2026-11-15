# Phone Setup (home Wi-Fi)

Your phone sends a brain-dump to Between on your Mac. Both must be on the same Wi-Fi.
Never paste the Shortcut URL into chats or files: it holds your phone token.

## 1. Start Between for the phone (on the Mac)

```bash
cd ~/projects/between
scripts/start-phone.sh
```

This listens on your Wi-Fi (not just this Mac). Requests from other devices need the phone token.
If macOS asks "Allow incoming connections?" for Python, click **Allow**.

## 2. Copy the Shortcut URL (on the Mac, in your own Terminal)

```bash
/usr/bin/python3 scripts/phone_link.py
```

It copies `http://<your-mac-ip>:8765/api/capture/<token>` to the clipboard and shows only the first 3 characters of the token.
Add `--new-token` to make a fresh token (any old Shortcut URL stops working).

## 3. Make the Shortcut (on the iPhone, Shortcuts app)

1. Tap **+** to make a new shortcut. Name it **Between**.
2. Add **Dictate Text**.
3. Add **Get Contents of URL**.
4. Tap the URL field and paste the Shortcut URL (Universal Clipboard), or AirDrop it to yourself.
5. Tap the arrow next to the URL. Set **Method** to **POST**.
6. Set **Request Body** to **JSON**. Add two text fields:
   - `text` → tap and pick the **Dictated Text** variable
   - `source` → type `phone`
7. Add **Show Notification** (optional) so you see that it worked.

## 4. Try it

Run the shortcut, say a task (for example "finish the essay outline by Friday, about an hour"), and check the dashboard on the Mac: it shows up under Your to-dos.

## Typing instead of talking

Replace **Dictate Text** with **Ask for Input** (type: Text) and pick **Provided Input** for `text`.

## If it doesn't work

- "Phone token required": the URL's token is old. Run step 2 again and paste the new URL.
- Nothing happens / times out: the phone isn't on the same Wi-Fi, the server isn't running with `start-phone.sh`, or the Mac's Wi-Fi address changed. Run step 2 again.

## Away from home

Later (build item 4): the hosted app with HTTPS. Not set up yet.
