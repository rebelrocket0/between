# Phone Setup

## Same Wi-Fi

Start the app so your phone can reach your Mac:

```bash
cd /Users/rebelrocket/Documents/Codex/2026-09-06/can-you-please/work/life-brain
python3 server.py --host 0.0.0.0
```

Open the app on your Mac and go to `Phone`. Copy one of the phone URLs, then open it on your iPhone while both devices are on the same Wi-Fi.

The URL contains a local phone token. After the first open, the phone stores the token in the browser and sends it with local app requests.

## Apple Shortcut Capture

Create a voice-only shortcut with this shape:

1. `Dictate Text` or `Ask for Input`.
2. `Get Contents of URL`.
3. Set method to `POST`.
4. Set request body to JSON.
5. Send:

```json
{
  "text": "Provided Input",
  "source": "phone"
}
```

Use the Shortcut endpoint from the Phone tab. It already includes the token and looks like:

```text
/api/capture/your-token
```

## Type Or Dictate

To use one shortcut for both typing and voice:

1. Add `Choose from Menu`.
2. Add two choices: `Type` and `Dictate`.
3. Under `Type`, add `Ask for Input` with input type `Text`.
4. Under `Dictate`, add `Dictate Text`.
5. In each branch, set a variable named `Brain Text` to the typed or dictated result.
6. After the menu, add `Get Contents of URL`.
7. Use the same JSON body:

```json
{
  "text": "Brain Text",
  "source": "phone"
}
```

## Away From Home

Use Tailscale later if you want phone capture when your phone is not on the same Wi-Fi as your Mac.
