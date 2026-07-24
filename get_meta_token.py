#!/usr/bin/env python3
"""
Meta Graph API Professional OAuth Token Setup Utility
=====================================================
A clean, automated, and professional local OAuth 2.0 authentication script for Meta Graph API.

Replaces the buggy Meta Graph API Explorer web UI by running a local OAuth callback server.

What this script does automatically (in ~10 seconds):
  1. Opens your browser to Meta's official OAuth consent screen with all required scopes pre-configured.
  2. Catches the authorization code on a local web server (http://localhost:8090).
  3. Exchanges the code for a Short-Lived User Access Token.
  4. Automatically converts it into a 60-Day Long-Lived User Token.
  5. Automatically discovers your connected Facebook Pages and Instagram Business Account IDs.
  6. Derives a NEVER-EXPIRING Page Access Token.
  7. Formats and updates your `.env` file automatically.

Prerequisites (One-Time Setup):
  1. Go to https://developers.facebook.com/apps/ and select/create your App.
  2. Under App Settings -> Basic, copy your "App ID" and "App Secret".
  3. Under Use Cases / Products -> Facebook Login -> Settings (or App Settings -> Basic -> Add Platform -> Website):
     Add `http://localhost:8090/` to your "Valid OAuth Redirect URIs".

Usage:
  python get_meta_token.py
"""

import os
import sys
import json
import time
import threading
import http.server
import urllib.parse
import urllib.request
import urllib.error
import webbrowser
from pathlib import Path
from typing import Dict, Any, Optional

REDIRECT_PORT = 8090
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/"
META_GRAPH_VER = os.environ.get("FB_GRAPH_VERSION", "v21.0")

# Standard permissions required for automated Instagram Graph API Reels publishing
# (Supported by Instagram Use Case Apps)
# pages_manage_posts is intentionally NOT requested: Meta's use-case dashboard
# no longer offers it to this app (2026-07-24), and requesting an unoffered
# scope hard-fails the OAuth dialog with "Invalid Scopes". The original grant
# persists on the user+app pair, so derived Page tokens still carry it —
# verify via the "Granted Scopes" printout before confirming the .env write.
REQUIRED_SCOPES = [
    "instagram_basic",
    "instagram_content_publish",
    "instagram_manage_insights",
    "pages_show_list",
    "pages_read_engagement"
]


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

auth_code_container: Dict[str, str] = {}

class OAuthCodeCallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        
        if "code" in params:
            auth_code_container["code"] = params["code"][0]
            html = """
            <!Color html>
            <html>
            <head><title>Meta OAuth Success</title></head>
            <body style="font-family: system-ui, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0;">
                <div style="background: #1e293b; padding: 40px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); text-align: center; max-width: 480px; border: 1px solid #334155;">
                    <div style="font-size: 48px; margin-bottom: 16px;">🎉</div>
                    <h1 style="color: #38bdf8; margin-top: 0;">Authorization Successful!</h1>
                    <p style="color: #94a3b8; font-size: 16px; line-height: 1.5;">Meta authentication code received. You can close this tab and return to your terminal.</p>
                </div>
            </body>
            </html>
            """
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
        elif "error" in params:
            err_desc = params.get("error_description", ["Unknown error"])[0]
            auth_code_container["error"] = err_desc
            html = f"""
            <!Color html>
            <html>
            <head><title>Meta OAuth Error</title></head>
            <body style="font-family: system-ui, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0;">
                <div style="background: #1e293b; padding: 40px; border-radius: 16px; text-align: center; max-width: 480px; border: 1px solid #ef4444;">
                    <div style="font-size: 48px; margin-bottom: 16px;">❌</div>
                    <h1 style="color: #f87171; margin-top: 0;">Authorization Failed</h1>
                    <p style="color: #94a3b8;">Error: {err_desc}</p>
                </div>
            </body>
            </html>
            """
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Quiet HTTP logs

def make_http_request(url: str, post_data: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Helper to execute HTTP GET/POST requests."""
    try:
        if post_data:
            data_bytes = urllib.parse.urlencode(post_data).encode("utf-8")
            req = urllib.request.Request(url, data=data_bytes, method="POST")
        else:
            req = urllib.request.Request(url, method="GET")
            
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            return json.loads(err_body)
        except Exception:
            return {"error": {"message": f"HTTP Error {e.code}: {err_body}"}}
    except Exception as ex:
        return {"error": {"message": str(ex)}}

def load_existing_env(env_path: str = ".env") -> Dict[str, str]:
    env_vars = {}
    p = Path(env_path)
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip().strip("'").strip('"')
    return env_vars

def update_env_file(updates: Dict[str, str], env_path: str = ".env"):
    p = Path(env_path)
    lines = []
    existing_keys = set()
    
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    k, _ = stripped.split("=", 1)
                    k = k.strip()
                    if k in updates:
                        lines.append(f"{k}={updates[k]}\n")
                        existing_keys.add(k)
                        continue
                lines.append(line)
                
    # Add any missing keys
    for k, v in updates.items():
        if k not in existing_keys:
            lines.append(f"{k}={v}\n")
            
    with open(p, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"{Colors.GREEN}[✓ SUCCESS]{Colors.RESET} Updated credentials in {env_path}")

def main():
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}  META GRAPH API PROFESSIONAL OAUTH TOKEN GENERATOR{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'=' * 70}{Colors.RESET}\n")

    env = load_existing_env()
    
    app_id = os.environ.get("FB_APP_ID") or env.get("FB_APP_ID") or ""
    app_secret = os.environ.get("FB_APP_SECRET") or env.get("FB_APP_SECRET") or ""

    if not app_id:
        app_id = input(f"{Colors.BOLD}Enter your Meta App ID (from developers.facebook.com): {Colors.RESET}").strip()
    else:
        print(f"Using App ID from environment/env: {Colors.BOLD}{app_id}{Colors.RESET}")

    if not app_secret:
        app_secret = input(f"{Colors.BOLD}Enter your Meta App Secret: {Colors.RESET}").strip()
    else:
        print(f"Using App Secret from environment/env: {Colors.BOLD}{app_secret[:6]}...{Colors.RESET}")

    if not app_id or not app_secret:
        print(f"{Colors.RED}[✗ ERROR]{Colors.RESET} App ID and App Secret are required.")
        sys.exit(1)

    # Construct Meta OAuth URL (auth_type=rerequest forces Meta to prompt for Page & IG Account selection)
    scope_str = ",".join(REQUIRED_SCOPES)
    auth_params = {
        "client_id": app_id,
        "redirect_uri": REDIRECT_URI,
        "scope": scope_str,
        "response_type": "code",
        "auth_type": "rerequest"
    }
    auth_url = f"https://www.facebook.com/{META_GRAPH_VER}/dialog/oauth?" + urllib.parse.urlencode(auth_params)

    # Direct Dashboard Link for enabling Use Case Permissions
    dashboard_usecase_url = f"https://developers.facebook.com/apps/{app_id}/use-cases/"

    print(f"\n{Colors.YELLOW}{Colors.BOLD}📌 IMPORTANT ONE-TIME STEP IN META DASHBOARD:{Colors.RESET}")
    print(f"If Meta displays '{Colors.RED}Invalid Scopes{Colors.RESET}' in your browser, ensure you have clicked '{Colors.BOLD}Add{Colors.RESET}' next to permissions in Meta Dashboard:")
    print(f"  1. Go to: {Colors.CYAN}{dashboard_usecase_url}{Colors.RESET}")
    print(f"  2. Click '{Colors.BOLD}Manage messages and content on Instagram{Colors.RESET}' -> '{Colors.BOLD}Customize{Colors.RESET}'")
    print(f"  3. Under '{Colors.BOLD}Permissions{Colors.RESET}', click '{Colors.GREEN}Add{Colors.RESET}' next to: {Colors.BOLD}instagram_basic{Colors.RESET} and {Colors.BOLD}instagram_content_publish{Colors.RESET}\n")

    # Start local HTTP server
    server = http.server.HTTPServer(("localhost", REDIRECT_PORT), OAuthCodeCallbackHandler)
    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    print(f"\n{Colors.BLUE}[i INFO]{Colors.RESET} Opening browser for Meta login (listening on {REDIRECT_URI})...")
    print(f"{Colors.DIM}If your browser does not open automatically, click this link:\n{auth_url}{Colors.RESET}\n")
    webbrowser.open(auth_url)

    # Wait for authorization code callback
    start_wait = time.time()
    while "code" not in auth_code_container and "error" not in auth_code_container:
        if time.time() - start_wait > 180:
            print(f"{Colors.RED}[✗ ERROR]{Colors.RESET} Timed out waiting for Meta authorization in browser (3 minutes).")
            server.server_close()
            sys.exit(1)
        time.sleep(0.5)

    server.server_close()

    if "error" in auth_code_container:
        print(f"{Colors.RED}[✗ ERROR]{Colors.RESET} OAuth Authorization Failed: {auth_code_container['error']}")
        sys.exit(1)

    code = auth_code_container["code"]
    print(f"{Colors.GREEN}[✓ SUCCESS]{Colors.RESET} Received authorization code from browser!")

    # Step 1: Exchange code for Short-Lived User Token
    print(f"{Colors.BLUE}[i INFO]{Colors.RESET} Step 1: Exchanging code for Short-Lived User Access Token...")
    token_url = f"https://graph.facebook.com/{META_GRAPH_VER}/oauth/access_token"
    token_params = {
        "client_id": app_id,
        "client_secret": app_secret,
        "redirect_uri": REDIRECT_URI,
        "code": code
    }
    token_res = make_http_request(token_url, post_data=token_params)

    if "error" in token_res:
        print(f"{Colors.RED}[✗ ERROR]{Colors.RESET} Token exchange failed: {token_res['error'].get('message', token_res)}")
        sys.exit(1)

    short_user_token = token_res["access_token"]
    print(f"{Colors.GREEN}[✓ SUCCESS]{Colors.RESET} Short-Lived User Access Token acquired.")

    # Step 2: Exchange Short-Lived Token for 60-Day Long-Lived User Token
    print(f"{Colors.BLUE}[i INFO]{Colors.RESET} Step 2: Exchanging for 60-Day Long-Lived User Access Token...")
    long_url = (
        f"https://graph.facebook.com/{META_GRAPH_VER}/oauth/access_token"
        f"?grant_type=fb_exchange_token"
        f"&client_id={app_id}"
        f"&client_secret={app_secret}"
        f"&fb_exchange_token={short_user_token}"
    )
    long_res = make_http_request(long_url)

    if "error" in long_res:
        print(f"{Colors.RED}[✗ ERROR]{Colors.RESET} Long-lived token exchange failed: {long_res['error'].get('message', long_res)}")
        sys.exit(1)

    long_user_token = long_res["access_token"]
    expires_in = long_res.get("expires_in", 0)
    days = expires_in // 86400 if expires_in else 60
    print(f"{Colors.GREEN}[✓ SUCCESS]{Colors.RESET} 60-Day Long-Lived User Token acquired (expires in ~{days} days)!")

    # Step 3: Discover Facebook Pages & Linked Instagram Accounts
    print(f"{Colors.BLUE}[i INFO]{Colors.RESET} Step 3: Discovering Facebook Pages & Instagram Business Accounts...")
    
    # Check granted permissions
    perm_url = f"https://graph.facebook.com/{META_GRAPH_VER}/me/permissions?access_token={urllib.parse.quote(long_user_token)}"
    perm_res = make_http_request(perm_url)
    granted = [p["permission"] for p in perm_res.get("data", []) if p.get("status") == "granted"]
    print(f"{Colors.DIM}  Granted Scopes: {', '.join(granted)}{Colors.RESET}")

    accounts_url = (
        f"https://graph.facebook.com/{META_GRAPH_VER}/me/accounts"
        f"?fields=id,name,category,access_token,instagram_business_account"
        f"&access_token={urllib.parse.quote(long_user_token)}"
    )
    acc_res = make_http_request(accounts_url)
    print(f"{Colors.DIM}  [DEBUG] /me/accounts raw response: {acc_res}{Colors.RESET}")
    pages = acc_res.get("data", [])

    # Also test /me?fields=id,name,instagram_business_account
    me_ig_url = f"https://graph.facebook.com/{META_GRAPH_VER}/me?fields=id,name,instagram_business_account&access_token={urllib.parse.quote(long_user_token)}"
    me_ig_res = make_http_request(me_ig_url)
    print(f"{Colors.DIM}  [DEBUG] /me?fields=id,name,instagram_business_account raw response: {me_ig_res}{Colors.RESET}")

    # Also test debug_token
    debug_url = f"https://graph.facebook.com/{META_GRAPH_VER}/debug_token?input_token={urllib.parse.quote(long_user_token)}&access_token={app_id}|{app_secret}"
    debug_res = make_http_request(debug_url)
    print(f"{Colors.DIM}  [DEBUG] debug_token response: {debug_res.get('data', {})}{Colors.RESET}")


    # Fallback Strategy: Auto-extract Page ID & IG Account ID directly from debug_token granular_scopes!
    if not pages:
        d_data = debug_res.get("data", {})
        g_scopes = d_data.get("granular_scopes", [])
        
        extracted_page_id = None
        extracted_ig_id = None
        
        for g in g_scopes:
            scope_name = g.get("scope")
            t_ids = g.get("target_ids", [])
            if t_ids:
                if scope_name in ("pages_show_list", "pages_read_engagement"):
                    extracted_page_id = t_ids[0]
                elif scope_name in ("instagram_basic", "instagram_content_publish"):
                    extracted_ig_id = t_ids[0]
                    
        if extracted_page_id:
            print(f"{Colors.GREEN}[✓ DISCOVERED]{Colors.RESET} Found Page ID in Token Scopes: {extracted_page_id}")
            p_url = (
                f"https://graph.facebook.com/{META_GRAPH_VER}/{extracted_page_id}"
                f"?fields=id,name,access_token,instagram_business_account"
                f"&access_token={urllib.parse.quote(long_user_token)}"
            )
            p_res = make_http_request(p_url)
            page_token = p_res.get("access_token") or long_user_token
            page_name = p_res.get("name") or "Neon Node"
            
            pages = [{
                "id": extracted_page_id,
                "name": page_name,
                "access_token": page_token,
                "instagram_business_account": {"id": extracted_ig_id} if extracted_ig_id else p_res.get("instagram_business_account", {})
            }]
            print(f"{Colors.GREEN}[✓ SUCCESS]{Colors.RESET} Auto-resolved Page: '{page_name}' (Page ID: {extracted_page_id} | IG ID: {extracted_ig_id})")


    if not pages:
        print(f"\n{Colors.YELLOW}[! NOTICE]{Colors.RESET} Auto-discovery via /me/accounts returned empty.")
        print(f"{Colors.YELLOW}📌 NEW PAGES EXPERIENCE TIP:{Colors.RESET} Switch your Facebook profile in browser to '{Colors.BOLD}Neon Node{Colors.RESET}' before approving authorization.")
        print("Paste your full Facebook Page URL (or numeric Page ID) below:")
        print(f"{Colors.DIM}  (Example: https://www.facebook.com/profile.php?id=1234567890){Colors.RESET}")
        default_page_id = os.environ.get("FB_PAGE_ID", "").strip()
        default_hint = f" [default: {default_page_id}]" if default_page_id else ""
        page_input = input(f"{Colors.BOLD}Paste Facebook Page URL or Page ID{default_hint}: {Colors.RESET}").strip() or default_page_id
        
        if page_input:
            extracted = page_input
            if "facebook.com/" in page_input:
                parsed_url = urllib.parse.urlparse(page_input)
                query_params = urllib.parse.parse_qs(parsed_url.query)
                if "id" in query_params:
                    extracted = query_params["id"][0]
                else:
                    path_parts = [p for p in parsed_url.path.strip("/").split("/") if p]
                    if path_parts:
                        extracted = path_parts[0]
                        
            candidates = [
                extracted,
                extracted.replace(" ", ""),
                extracted.replace(" ", ".").lower(),
                extracted.replace(" ", "_").lower()
            ]
            
            for cand in candidates:
                p_url = (
                    f"https://graph.facebook.com/{META_GRAPH_VER}/{urllib.parse.quote(cand)}"
                    f"?fields=id,name,access_token,instagram_business_account"
                    f"&access_token={urllib.parse.quote(long_user_token)}"
                )
                p_res = make_http_request(p_url)
                if "error" not in p_res and p_res.get("id"):
                    pages = [p_res]
                    print(f"{Colors.GREEN}[✓ SUCCESS]{Colors.RESET} Resolved Facebook Page: '{p_res.get('name')}' (ID: {p_res.get('id')})")
                    break
            else:
                print(f"{Colors.RED}[✗ ERROR]{Colors.RESET} Could not resolve Page from '{page_input}': {p_res.get('error', {}).get('message', p_res)}")

    if not pages:
        print(f"{Colors.RED}[✗ ERROR]{Colors.RESET} No Facebook Pages could be resolved for this account.")
        sys.exit(1)




    print(f"\n{Colors.BOLD}Found {len(pages)} Facebook Page(s):{Colors.RESET}\n")


    selected_page = pages[0]
    if len(pages) > 1:
        for idx, p in enumerate(pages, 1):
            ig_b = p.get("instagram_business_account", {})
            ig_id_str = ig_b.get("id") if isinstance(ig_b, dict) else "None"
            print(f"  {idx}. Page: {Colors.BOLD}{p.get('name')}{Colors.RESET} (Page ID: {p.get('id')}) | IG Account ID: {ig_id_str}")
        sel_idx = input(f"\nSelect Page number (1-{len(pages)}, default 1): ").strip()
        if sel_idx.isdigit() and 1 <= int(sel_idx) <= len(pages):
            selected_page = pages[int(sel_idx) - 1]

    page_id = selected_page.get("id")
    page_name = selected_page.get("name")
    page_access_token = selected_page.get("access_token")  # NON-EXPIRING PAGE TOKEN!
    ig_biz = selected_page.get("instagram_business_account", {})
    ig_account_id = ig_biz.get("id") if isinstance(ig_biz, dict) else ""

    print(f"\n{Colors.CYAN}{Colors.BOLD}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}  OAUTH SETUP COMPLETE & VERIFIED!{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'=' * 70}{Colors.RESET}\n")

    print(f"📌 {Colors.BOLD}Selected Page:{Colors.RESET}                  {page_name}")
    print(f"📌 {Colors.BOLD}FB_PAGE_ID:{Colors.RESET}                     {page_id}")
    print(f"📌 {Colors.BOLD}INSTAGRAM_BUSINESS_ACCOUNT_ID:{Colors.RESET} {ig_account_id or Colors.YELLOW + 'Not Linked' + Colors.RESET}")
    print(f"📌 {Colors.BOLD}Token Type:{Colors.RESET}                    Never-Expiring Page Access Token")
    print(f"📌 {Colors.BOLD}FB_ACCESS_TOKEN_TECH:{Colors.RESET}          {page_access_token[:15]}...{page_access_token[-6:]}\n")

    # Ask to write to .env
    env_updates = {
        "INSTAGRAM_TECH_METHOD": "official",
        "FB_APP_ID": app_id,
        "FB_APP_SECRET": app_secret,
        "FB_PAGE_ID": page_id,
        "FB_ACCESS_TOKEN_TECH": page_access_token,
        "FB_PAGE_ACCESS_TOKEN": page_access_token,
        "ENABLE_INSTAGRAM_AUTOPOST": "true",
        "ENABLE_FACEBOOK_AUTOPOST": "true"
    }
    if ig_account_id:
        env_updates["INSTAGRAM_TECH_BUSINESS_ACCOUNT_ID"] = ig_account_id

    confirm = input(f"{Colors.BOLD}Do you want to write these credentials to .env automatically? (Y/n): {Colors.RESET}").strip()
    if confirm.lower() != 'n':
        update_env_file(env_updates)
        print(f"\n{Colors.GREEN}{Colors.BOLD}✅ Your system is now 100% configured for official Meta Graph API publishing!{Colors.RESET}")
        print(f"You can now run: {Colors.CYAN}python test_meta_graph_api.py --inspect{Colors.RESET}")
    else:
        print("\nCopy these values into your .env file manually:")
        for k, v in env_updates.items():
            print(f"{k}={v}")

if __name__ == "__main__":
    main()
