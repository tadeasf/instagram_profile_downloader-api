import requests
import os
from dotenv import load_dotenv

load_dotenv()
user = os.getenv("USERNAME1")
password = os.getenv("PASSWORD1")

url = "http://localhost:8001/highlights/whostoletedsusername/0"

querystring = {"user":user,"password":password}

payload = ""
response = requests.request("GET", url, data=payload, params=querystring)

print(response.text)