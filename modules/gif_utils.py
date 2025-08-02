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
    
def get_gif_by_id(gif_id: str):
    """Fetches a single GIF from Tenor by its ID."""
    apikey = os.getenv('GIF')
    ckey = "my_test_app"
    try:
        response = requests.get(
            f"https://tenor.googleapis.com/v2/posts?ids={gif_id}&key={apikey}&client_key={ckey}&media_filter=gif")
        response.raise_for_status()
        data = response.json()
        if (results := data.get("results")) and results:
            # Extract the URL for the 'gif' format
            return results[0].get("media_formats", {}).get("gif", {}).get("url")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error occurred fetching GIF by ID '{gif_id}': {e}")
        return None
