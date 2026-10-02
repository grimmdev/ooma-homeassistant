"""
Test harness for Ooma Client.
Usage: python test_client.py <PHONE_OR_USERNAME> <PASSWORD>
"""

import asyncio
import sys
import logging
from ooma_client import OomaClient, OomaAuthError, OomaConnectionError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

async def main():
    if len(sys.argv) < 3:
        print("Usage: python test_client.py <PHONE_OR_USERNAME> <PASSWORD>")
        print("Example: python test_client.py 5551234567 MySecretPass")
        return

    username = sys.argv[1]
    password = sys.argv[2]

    print(f"[*] Testing Ooma Client for user: {username}...")
    async with OomaClient(username=username, password=password) as client:
        try:
            print("[*] Authenticating with my.ooma.com...")
            await client.login()
            print("[+] Login Successful!")

            print("[*] Fetching call logs...")
            logs = await client.get_call_logs(limit=5)
            print(f"[+] Retrieved {len(logs)} call logs:")
            for log in logs:
                print(f"    - [{log.get('direction', '').upper()}] {log.get('name')} ({log.get('number')}) at {log.get('timestamp')} - Duration: {log.get('duration')}")

            print("[*] Fetching voicemails...")
            vms = await client.get_voicemails()
            print(f"[+] Voicemails: Unread={vms.get('unread_count')}, Total={vms.get('total_count')}")

            print("[*] Fetching account summary...")
            summary = await client.get_account_summary()
            print(f"[+] Account Summary: {summary}")

        except OomaAuthError as e:
            print(f"[-] Authentication Failed: {e}")
        except OomaConnectionError as e:
            print(f"[-] Network Connection Error: {e}")
        except Exception as e:
            print(f"[!] Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
