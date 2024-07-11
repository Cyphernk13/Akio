from meta_ai_api import MetaAI
from dotenv import load_dotenv
import os

load_dotenv()
Fb_Email = os.getenv('FB_Email')
Fb_Password = os.getenv('FB_Password')
ai_instance = MetaAI(fb_email=Fb_Email, fb_password=Fb_Password)

# Prebuilt message to ensure AI acts as 'Akio'
prebuilt_message = "You have to act like a cute discord bot named Akio. Only when asked, say your name is Akio, don't state your name out of the blue. Now the user will give a query: "

async def ai(user_input: str) -> str:
    try:
        # Combine prebuilt message with user input
        combined_input = f"{prebuilt_message} {user_input}"
        
        response = ai_instance.prompt(message=combined_input)
        # print(f"MetaAI response: {response}")  # Debugging line

        if isinstance(response, dict):
            if 'message' in response and response['message'].strip():
                return response['message']
            elif 'media' in response and response['media']:  
                return response['media'][0]['url']
        elif isinstance(response, str):
            return response 

        return "Sorry, I couldn't generate a response."
    
    except Exception as e:
        # print(f"Exception occurred: {e}")  # Debugging line
        return f"An error occurred: {e}"
