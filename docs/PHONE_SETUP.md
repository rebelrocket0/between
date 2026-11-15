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
/usr/bin/python3 scripts/phone_link.py --new-token
```

Run this in your own Terminal: it rotates the stale token mentioned in the handoff and copies the new URL to the clipboard. Any old Shortcut URL stops working; the running server reads the new token without a restart.

The URL uses `http://<your-mac-local-hostname>.local:8765/api/capture/<token>`. The helper finds the Mac's actual Bonjour name; don't assume it is `mac.local`. Its terminal output masks the token. Never paste the URL or a screenshot of it into chat.

After this one rotation, omit `--new-token` whenever you only need to copy the current URL again.

## 3. Make the Shortcut (on the iPhone, Shortcuts app)

If you already have **local brain capture** with a Type/Dictate menu, keep it:

1. Paste the newly copied URL into **both** Get Contents of URL actions, replacing the entire old URL.
2. In each action, set **Method** to **POST** and **Request Body** to **JSON**.
3. Keep `text` connected to the branch's **Provided Input** or **Dictated Text** variable, and `source` set to `phone`.
4. Keep the header **Content-Type: application/json** and remove the empty header row.

For a new dictation-only shortcut:

1. Tap **+** to make a new shortcut. Name it **Between**.
2. Add **Dictate Text**.
3. Add **Get Contents of URL**.
4. Tap the URL field and paste the Shortcut URL (Universal Clipboard), or AirDrop it to yourself.
5. Tap the arrow next to the URL. Set **Method** to **POST**.
6. Set **Request Body** to **JSON**. Add two text fields:
   - `text` → tap and pick the **Dictated Text** variable
   - `source` → type `phone`
7. Set the header **Content-Type** to **application/json**. Remove any empty header row.
8. Add **Show Notification** (optional). Confirm success on the dashboard; a notification alone does not prove capture succeeded.

## 4. Try it

With both devices on home Wi-Fi, run the shortcut → **Dictate** → say "read chapter 4 for 20 minutes". Reload the dashboard on the Mac and confirm the task appears under Your to-dos. Then try the **Type** branch to verify its separate URL action too.

This creates real tasks and may trigger the normal Google sync. The phone step is complete only after the captures appear on the dashboard; Mac-side automated tests do not verify iPhone connectivity.

## Typing instead of talking

Replace **Dictate Text** with **Ask for Input** (type: Text) and pick **Provided Input** for `text`.

## If it doesn't work

- "Phone token required": the URL's token is old. Run step 2 again and paste the new URL.
- Nothing happens / times out: check that both devices are on the same Wi-Fi, the Mac is awake, and the server is running with `start-phone.sh` on port 8765.
- If the `.local` name cannot be reached, run `/usr/bin/python3 scripts/phone_link.py --ip` and replace the URL in both actions. Some campus or guest Wi-Fi networks block device-to-device access; use home Wi-Fi for this test. An IP-based URL needs updating when the Mac's address changes.

## Away from home

Later: the hosted app with HTTPS. Deployment is deferred until the user authorizes AWS setup.
