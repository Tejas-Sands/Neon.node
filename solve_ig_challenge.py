import os
import json
from instagrapi import Client

def get_code(username, choice):
    print(f"\n[!] Instagram is requesting a security code for {username}.")
    if choice == 1:
        return input("Enter the code sent to your SMS: ")
    elif choice == 2:
        return input("Enter the code sent to your Email: ")
    return input("Enter the verification code: ")

def main():
    print("Loading .env credentials...")
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    key, _, val = line.partition("=")
                    if key.strip() and key.strip() not in os.environ:
                        os.environ[key.strip()] = val.strip().strip("'\"")

    username = os.environ.get("INSTAGRAM_TECH_USERNAME", "")
    password = os.environ.get("INSTAGRAM_TECH_PASSWORD", "")

    if not username or not password:
        print("Error: Could not find INSTAGRAM_TECH_USERNAME and INSTAGRAM_TECH_PASSWORD in .env")
        return

    cl = Client()
    cl.delay_range = [2, 5]
    
    # This handler allows instagrapi to prompt you for the code
    cl.challenge_code_handler = get_code
    
    print(f"\nAttempting to login as {username}...")
    try:
        # We will attempt a fresh login and solve the challenge
        cl.login(username, password)
        cl.dump_settings("instagram_session.json")
        print("\n✅ Login successful! Session saved to instagram_session.json.")
        print("You can now run 'python post_now.py' again.")
    except Exception as e:
        print(f"\n❌ Login failed: {e}")

if __name__ == "__main__":
    main()
