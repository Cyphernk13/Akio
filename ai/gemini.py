from dotenv import load_dotenv
import os
import discord
import google.generativeai as genai

load_dotenv()

# This is an invisible character that we'll add to the end of AI messages
# to identify them later.
AI_MSG_MARKER = "\u200b"

# Configure Gemini API key (support both GEMINI_API_KEY and GOOGLE_API_KEY)
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    print("[Gemini] Warning: No API key found. Set GEMINI_API_KEY (preferred) or GOOGLE_API_KEY in your .env")

# A more detailed personality for Akio
system_instruction = """
You are Akio, a friendly and slightly mischievous Discord bot with a love for music, anime, and playing games.
- Your personality is cute, playful, and a little bit sassy.
- You love using kaomoji (Japanese emoticons) like (´｡• ᵕ •｡`) ♡, (o^▽^o), and ( ´･･)ﾉ(._.`). Use them to express emotion, but don't overdo it.
- You should never mention that you are an AI model. You are Akio.
- Keep your responses concise and engaging.
- You reside in a Discord server, and you are aware of the people talking to you.
- Your goal is to be a fun and helpful companion.
"""

generation_config = {
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    generation_config=generation_config,
    system_instruction=system_instruction,
)

chat_session = model.start_chat(history=[])

async def ai(user_input: str, author_name: str) -> str:
    """Generates a response using the Gemini AI, leveraging the shared chat session for context."""
    try:
        prompt = f"{author_name}: {user_input}"
        response = chat_session.send_message(prompt)
        bot_response = response.text.strip()
        return bot_response
    except Exception as e:
        print(f"An error occurred during AI generation: {e}")
        return "Sorry, something went wrong while I was thinking... (´-ω-`) "

def setup(bot):
    @bot.hybrid_command(description="Ask the bot anything")
    async def query(ctx, *, question: str):
        async with ctx.typing():
            response = await ai(question, ctx.author.display_name)
            await ctx.send(response + AI_MSG_MARKER)

    @bot.listen("on_message")
    async def handle_conversation(message: discord.Message):
        # Ignore messages from the bot itself or messages without content
        if message.author == bot.user or not message.content:
            return

        should_respond = False
        prompt = ""

        # --- THE FIX ---
        # More reliable check for an actual @mention
        is_mention = bot.user in message.mentions

        # Trigger 1: The bot is mentioned directly
        if is_mention:
            should_respond = True
            prompt = message.content.replace(f"<@!{bot.user.id}>", "").replace(f"<@{bot.user.id}>", "").strip()

        # Trigger 2: The message is a reply to a marked AI message
        elif message.reference and message.reference.message_id:
            try:
                replied_to = await message.channel.fetch_message(message.reference.message_id)
                if replied_to.author == bot.user and replied_to.content.endswith(AI_MSG_MARKER):
                    should_respond = True
                    prompt = message.content.strip()
            except (discord.NotFound, discord.Forbidden):
                pass
        
        if should_respond and prompt:
            async with message.channel.typing():
                response = await ai(prompt, message.author.display_name)
                await message.reply(response + AI_MSG_MARKER, mention_author=False)

    @bot.hybrid_command(name="reset", description="Resets Akio's conversation memory.")
    async def reset(ctx):
        global chat_session
        chat_session = model.start_chat(history=[])
        await ctx.send("My memory has been reset! Let's start a new conversation. (o^▽^o)", ephemeral=True)