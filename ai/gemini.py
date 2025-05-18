# from meta_ai_api import MetaAI

from dotenv import load_dotenv
import os

load_dotenv()

# ai_instance = MetaAI()

prebuilt_message = "You have to act like a cute discord bot named Akio. Only when asked, say your name is Akio, don't state your name out of the blue and don't use emojis, you can use emoticons but not too frequently but be creative and interactive :D. Now the user will give a query: "
conversation_history = prebuilt_message  # Initialize with the prebuilt message


import os
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Create the model
generation_config = {
  "temperature": 0.7,
  "top_p": 0.95,
  "top_k": 64,
  "max_output_tokens": 65536,
  "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
  model_name="gemini-2.0-flash-thinking-exp-01-21",
  generation_config=generation_config,
  system_instruction=prebuilt_message
)

chat_session = model.start_chat(
  history=[
  ]
)
# print(response.text)

async def ai(user_input: str) -> str:
    global conversation_history  # Access the conversation history

    try:
        # Add the new user input to the conversation history
        conversation_history += f"\nUser: {user_input}"
        
        print(f"Debug: Sending prompt -> {conversation_history}")
        # Send the full conversation history as a prompt to retain context

        response = chat_session.send_message(user_input)
        response = response.text.strip()
        print(f"Debug: Received response -> {response}")  # Add this to log API output
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
        print(f"An error occurred: {e}")
        return ""
    
def setup(bot):
    @bot.hybrid_command(description="Ask the bot anything")
    async def query(ctx, *, question: str):
        response = await ai(question)
        await ctx.send(response)

    @bot.listen("on_message")
    async def handle_mentions(message):
        if message.author == bot.user:
            return
        if bot.user in message.mentions:
            question = message.content.replace(f"<@{bot.user.id}>", "").strip()
            response = await ai(question)
            await message.channel.send(response)