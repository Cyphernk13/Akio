import os
import requests
from dotenv import load_dotenv
load_dotenv()

def get_top_8_gifs(query):
    apikey = os.getenv('GIF') # Ensure this is your correct API key
    lmt = 30
    ckey = "my_test_app"
    try:
        response = requests.get(
            "https://tenor.googleapis.com/v2/search?q=%s&key=%s&client_key=%s&limit=%s" % (query, apikey, ckey, lmt))
        response.raise_for_status()
        data = response.json()
        gifs = data.get("results", [])
        top_8_gifs = [gif["media_formats"]["gif"]["url"] for gif in gifs]
        return top_8_gifs
    except requests.exceptions.RequestException as e:
        print(f"Error occurred: {e}")
        return []
