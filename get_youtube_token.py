"""One-time helper: obtain a YouTube OAuth REFRESH TOKEN for automated uploads.

The auto-posting pipeline uploads Shorts via the official YouTube Data API v3,
which needs a long-lived refresh token. Run this ONCE on your local machine:

    python get_youtube_token.py

Prerequisites (5 minutes, one time):
  1. https://console.cloud.google.com → create a project (or reuse one).
  2. "APIs & Services" → Library → enable "YouTube Data API v3".
  3. "APIs & Services" → OAuth consent screen → External → add yourself as a
     test user (the app can stay in "Testing" mode for personal use).
  4. "APIs & Services" → Credentials → Create credentials → OAuth client ID →
     Application type: "Desktop app". Copy the client ID + secret.
  5. Run this script, paste them, approve in the browser window.

The script prints YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN lines —
put them in .env (local) or the HF Space / GitHub Actions secrets.

NOTE on API quota: uploads cost 1,600 units of the default 10,000/day quota,
so ~6 uploads/day max — which matches the 5-6 posts/day target.
NOTE on visibility: while your OAuth app is unverified, YouTube may lock
API-uploaded videos to PRIVATE. If that happens, request the (free) API audit
/ app verification in the Cloud Console, or start with YT_PRIVACY_STATUS=private
and flip videos public manually until verification lands.
"""
import http.server
import json
import threading
import urllib.parse
import urllib.request
import webbrowser

SCOPE = "https://www.googleapis.com/auth/youtube.upload"
REDIRECT_PORT = 8090
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}"

auth_code_holder = {}


class _CodeCatcher(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if "code" in params:
            auth_code_holder["code"] = params["code"][0]
            body = b"<h2>Authorized! You can close this tab and return to the terminal.</h2>"
        else:
            body = b"<h2>No code received. Check the terminal.</h2>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main():
    client_id = input("Paste your OAuth Client ID: ").strip()
    client_secret = input("Paste your OAuth Client Secret: ").strip()

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",   # <- this is what yields a refresh_token
        "prompt": "consent",        # <- force refresh_token even on re-auth
    })

    server = http.server.HTTPServer(("localhost", REDIRECT_PORT), _CodeCatcher)
    threading.Thread(target=server.handle_request, daemon=True).start()

    print(f"\nOpening browser for Google sign-in (listening on {REDIRECT_URI})...")
    print(f"If the browser doesn't open, visit:\n{auth_url}\n")
    webbrowser.open(auth_url)

    while "code" not in auth_code_holder:
        pass
    server.server_close()

    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "code": auth_code_holder["code"],
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data=data, timeout=30) as resp:
        tokens = json.loads(resp.read().decode())

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        print("ERROR: no refresh_token in response — remove the app's prior grant at "
              "https://myaccount.google.com/permissions and run again.")
        print(json.dumps(tokens, indent=2))
        return

    print("\n✅ Success! Add these to your .env / HF Space secrets / GitHub secrets:\n")
    print(f"YT_CLIENT_ID={client_id}")
    print(f"YT_CLIENT_SECRET={client_secret}")
    print(f"YT_REFRESH_TOKEN={refresh_token}")
    print("ENABLE_YOUTUBE_AUTOPOST=true")


if __name__ == "__main__":
    main()
