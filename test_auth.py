import instaloader
from dotenv import load_dotenv
import os

load_dotenv()

user = os.getenv("USERNAME1")
password = os.getenv("PASSWORD1")

def test_instaloader_auth():
    L = instaloader.Instaloader()
    try:
        L.login(user, password)
        print("Authentication successful")
    except instaloader.exceptions.BadCredentialsException:
        print("Authentication failed: Invalid credentials")

if __name__ == "__main__":
    test_instaloader_auth()