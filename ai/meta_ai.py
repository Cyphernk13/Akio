from meta_ai_api import MetaAI
from dotenv import load_dotenv
import os

load_dotenv()

ai_instance = MetaAI()

prebuilt_message = "You have to act like a cute discord bot named Akio. Only when asked, say your name is Akio, don't state your name out of the blue. Now the user will give a query: "
conversation_history = prebuilt_message  # Initialize with the prebuilt message

async def ai(user_input: str) -> str:
    global conversation_history  # Access the conversation history

    try:
        # Add the new user input to the conversation history
        conversation_history += f"\nUser: {user_input}"

        # Send the full conversation history as a prompt to retain context
        response = ai_instance.prompt(message=conversation_history)

        # Process the response
        if isinstance(response, dict) and 'message' in response:
            bot_response = response['message'].strip()
            conversation_history += f"\nAkio: {bot_response}"  # Append the bot's response to the history
            return bot_response
        elif isinstance(response, dict) and 'media' in response and response['media']:
            media_url = response['media'][0]['url']
            conversation_history += f"\nAkio: [Media response: {media_url}]"  # Log media response
            return media_url
        elif isinstance(response, str):
            conversation_history += f"\nAkio: {response}"
            return response

        return "Sorry, I couldn't generate a response."
    
    except Exception as e:
        return f"An error occurred: {e}"
