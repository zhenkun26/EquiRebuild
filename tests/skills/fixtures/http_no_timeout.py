import httpx
import requests

client = httpx.Client()
response = requests.get("https://example.com")
