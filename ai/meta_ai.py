import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()

genai.configure(api_key="AIzaSyB1S8rGxGv9E7wQ1Hu1V7iss3F13Zydr8Q")
model = genai.GenerativeModel("gemini-2.0-flash-exp")

prebuilt_message = "You are a cute friendly discord bot. Your name is Akio. The user will give you a query, answer it in a friendly manner. Do not state your name unless asked, like don't say. You don't have to write ""Akio:"" before the sentence, just answer the query. Now the user will ask you a question- "
conversation_history = prebuilt_message  # Initialize with the prebuilt message

async def ai(user_input: str) -> str:
    global conversation_history  # Access the conversation history

    try:
        # Add the new user input to the conversation history
        conversation_history += f"\nUser: {user_input}"

        # Send the full conversation history as a prompt to retain context
        response = model.generate_content(conversation_history)
        
        if response and hasattr(response, 'text'):
            bot_response = response.text.strip()
            conversation_history += f"\nAkio: {bot_response}"  # Append the bot's response to the history
            return bot_response
        
        return "Sorry, I couldn't generate a response."
    
    except Exception as e:
        return f"An error occurred: {e}"