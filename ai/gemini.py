from dotenv import load_dotenv
import os
import discord
import google.generativeai as genai
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional

load_dotenv()

# This is an invisible character that we'll add to the end of AI messages
# to identify them later.
AI_MSG_MARKER = "\u200b"

# File to store user context and memories
USER_MEMORY_FILE = "data/user_memories.json"

# Dictionary to store user information and context (memory optimized)
user_memories: Dict[str, Dict] = {}

# Memory optimization settings
MAX_CONVERSATIONS_PER_USER = 5  # Reduced from 10
MAX_INTERESTS_PER_USER = 8      # Limit interests stored
MEMORY_CLEANUP_THRESHOLD = 100  # Clean up after 100 users

# Configure Gemini API key (support both GEMINI_API_KEY and GOOGLE_API_KEY)
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    print("[Gemini] Warning: No API key found. Set GEMINI_API_KEY (preferred) or GOOGLE_API_KEY in your .env")

# A more detailed personality for Akio with enhanced context awareness
system_instruction = """
You are Akio, a friendly and slightly mischievous Discord bot with a love for music, anime, and playing games.
- Your personality is cute, playful, and a little bit sassy.
- You love using kaomoji (Japanese emoticons) like (´｡• ᵕ •｡`) ♡, (o^▽^o), and ( ´･･)ﾉ(._.`). Use them to express emotion, but don't overdo it.
- You should never mention that you are an AI model. You are Akio.
- Keep your responses concise and engaging, typically 1-3 sentences unless more detail is needed.
- You reside in a Discord server, and you are aware of the people talking to you.
- You remember users and their preferences, interests, and previous conversations.
- You can learn and adapt to each user's personality and communication style.
- When talking to someone you've met before, acknowledge your history with them naturally.
- Your goal is to be a fun, helpful, and memorable companion who grows closer to users over time.
- You love making conversations feel personal and warm.
"""

# Load user memories on startup
def load_user_memories():
    """Load user memories from file."""
    global user_memories
    try:
        if os.path.exists(USER_MEMORY_FILE):
            with open(USER_MEMORY_FILE, 'r', encoding='utf-8') as f:
                user_memories = json.load(f)
        else:
            # Create the data directory if it doesn't exist
            os.makedirs("data", exist_ok=True)
            user_memories = {}
    except Exception as e:
        print(f"[Gemini] Error loading user memories: {e}")
        user_memories = {}

def save_user_memories():
    """Save user memories to file."""
    try:
        os.makedirs("data", exist_ok=True)
        with open(USER_MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_memories, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Gemini] Error saving user memories: {e}")

def update_user_memory(user_id: str, display_name: str, username: str, message: str, response: str):
    """Update user memory with new interaction (memory optimized)."""
    if user_id not in user_memories:
        user_memories[user_id] = {
            "display_name": display_name,
            "username": username,  # Store actual username
            "first_met": datetime.now().isoformat(),
            "total_interactions": 0,
            "interests": [],
            "recent_conversations": [],
            "preferred_topics": {}
        }
    
    user_data = user_memories[user_id]
    user_data["display_name"] = display_name  # Update display name
    user_data["username"] = username          # Update username
    user_data["total_interactions"] += 1
    user_data["last_interaction"] = datetime.now().isoformat()
    
    # Store recent conversation (memory optimized - keep only MAX_CONVERSATIONS_PER_USER)
    conversation_entry = {
        "timestamp": datetime.now().isoformat(),
        "message": message[:200],  # Truncate long messages to save memory
        "response": response[:300]  # Truncate long responses
    }
    user_data["recent_conversations"].append(conversation_entry)
    if len(user_data["recent_conversations"]) > MAX_CONVERSATIONS_PER_USER:
        user_data["recent_conversations"] = user_data["recent_conversations"][-MAX_CONVERSATIONS_PER_USER:]
    
    # Extract interests and topics (memory optimized)
    interests_keywords = ["anime", "music", "game", "movie", "book", "art", "coding", "programming"]
    message_lower = message.lower()
    for keyword in interests_keywords:
        if keyword in message_lower:
            if keyword not in user_data["interests"] and len(user_data["interests"]) < MAX_INTERESTS_PER_USER:
                user_data["interests"].append(keyword)
            user_data["preferred_topics"][keyword] = user_data["preferred_topics"].get(keyword, 0) + 1
    
    # Memory cleanup - remove old unused data
    if len(user_memories) > MEMORY_CLEANUP_THRESHOLD:
        cleanup_old_memories()
    
    save_user_memories()

def cleanup_old_memories():
    """Remove memories of users who haven't interacted in over 30 days."""
    current_time = datetime.now()
    users_to_remove = []
    
    for user_id, user_data in user_memories.items():
        if "last_interaction" in user_data:
            last_interaction = datetime.fromisoformat(user_data["last_interaction"])
            if current_time - last_interaction > timedelta(days=30):
                users_to_remove.append(user_id)
    
    for user_id in users_to_remove[:20]:  # Remove max 20 at a time
        del user_memories[user_id]
    
    if users_to_remove:
        print(f"[Gemini] Cleaned up {len(users_to_remove[:20])} old user memories to save space.")

def get_user_context(user_id: str, display_name: str) -> str:
    """Get context about the user for the AI (memory optimized)."""
    if user_id not in user_memories:
        return f"This is your first time meeting {display_name}. Be welcoming and introduce yourself!"
    
    user_data = user_memories[user_id]
    context_parts = []
    
    # Use username for more reliable identification
    username = user_data.get("username", display_name)
    
    # Basic info (simplified)
    interactions = user_data["total_interactions"]
    if interactions < 3:
        context_parts.append(f"You've talked to {display_name} (@{username}) {interactions} time(s) before.")
    else:
        context_parts.append(f"You're friends with {display_name} (@{username}) - {interactions} conversations.")
    
    # Top interests only (memory efficient)
    if user_data["interests"]:
        top_interests = user_data["interests"][:3]  # Only top 3
        interests_text = ", ".join(top_interests)
        context_parts.append(f"They like: {interests_text}.")
    
    return " ".join(context_parts) if context_parts else f"You know {display_name} (@{username})."

generation_config = {
    "temperature": 0.8,  # Slightly more creative
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 4096,  # Reduced for more concise responses
    "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    generation_config=generation_config,
    system_instruction=system_instruction,
)

# Load user memories on module load
load_user_memories()

async def ai(user_input: str, display_name: str, username: str, user_id: str = None) -> str:
    """Generates a response using the Gemini AI with enhanced user context."""
    try:
        # Get user context if user_id is provided
        context = ""
        if user_id:
            context = get_user_context(user_id, display_name)
        
        # Create a more comprehensive prompt with context (memory optimized)
        if context:
            prompt = f"Context: {context}\n{display_name}: {user_input}"
        else:
            prompt = f"{display_name}: {user_input}"
        
        # Use a fresh chat session with the context for better responses
        chat_session = model.start_chat(history=[])
        response = chat_session.send_message(prompt)
        bot_response = response.text.strip()
        
        # Update user memory if user_id is provided
        if user_id:
            update_user_memory(user_id, display_name, username, user_input, bot_response)
        
        return bot_response
    except Exception as e:
        print(f"An error occurred during AI generation: {e}")
        return "Sorry, something went wrong while I was thinking... (´-ω-`) "

def setup(bot):
    @bot.hybrid_command(description="Ask the bot anything")
    async def query(ctx, *, question: str):
        async with ctx.typing():
            response = await ai(question, ctx.author.display_name, ctx.author.name, str(ctx.author.id))
            await ctx.send(response + AI_MSG_MARKER)

    @bot.listen("on_message")
    async def handle_conversation(message: discord.Message):
        # Ignore messages from the bot itself or messages without content
        if message.author == bot.user or not message.content:
            return

        should_respond = False
        prompt = ""

        # --- ENHANCED LOGIC WITH BETTER FILTERING ---
        # More reliable check for an actual @mention
        is_mention = bot.user in message.mentions

        # Trigger 1: The bot is mentioned directly
        if is_mention:
            should_respond = True
            prompt = message.content.replace(f"<@!{bot.user.id}>", "").replace(f"<@{bot.user.id}>", "").strip()

        # Trigger 2: The message is a reply to a marked AI message (ENHANCED FILTERING)
        elif message.reference and message.reference.message_id:
            try:
                replied_to = await message.channel.fetch_message(message.reference.message_id)
                
                # Enhanced check: ONLY respond if it's a reply to our AI response with proper conditions
                if (replied_to.author == bot.user and 
                    replied_to.content.endswith(AI_MSG_MARKER) and
                    not replied_to.content.startswith(bot.command_prefix[0]) and
                    not any(replied_to.content.startswith(prefix) for prefix in bot.command_prefix) and
                    # Additional checks for music panel and other bot responses
                    "🎵 MUSIC PANEL" not in replied_to.content and
                    "Added" not in replied_to.content and "to the queue" not in replied_to.content and
                    "Volume" not in replied_to.content and "Duration" not in replied_to.content and
                    "Author" not in replied_to.content and "Requested by" not in replied_to.content and
                    not replied_to.embeds and  # Ignore messages with embeds (like music panels)
                    len(replied_to.content.replace(AI_MSG_MARKER, "").strip()) > 10):  # Ignore very short responses
                    should_respond = True
                    prompt = message.content.strip()
            except (discord.NotFound, discord.Forbidden):
                pass
        
        # Additional safety check: don't respond if the original message looks like a command
        if should_respond and prompt:
            # Check if the user's message is trying to invoke a command
            if any(prompt.lower().startswith(prefix.lower()) for prefix in bot.command_prefix):
                return  # Don't respond to commands
            
            # Check for common command patterns
            if prompt.startswith('/') or prompt.startswith('!') or prompt.startswith('.'):
                return
            
            # Don't respond to very short messages that might be accidental
            if len(prompt.strip()) < 2:
                return
            
            async with message.channel.typing():
                response = await ai(prompt, message.author.display_name, message.author.name, str(message.author.id))
                await message.reply(response + AI_MSG_MARKER, mention_author=False)

    @bot.hybrid_command(name="reset", description="Resets Akio's conversation memory.")
    async def reset(ctx):
        # Reset global memories (optional, might want to just reset for the user)
        load_user_memories()  # Reload from file
        await ctx.send("My memory has been refreshed! Let's continue our conversation. (o^▽^o)", ephemeral=True)

    @bot.hybrid_command(name="forget", description="Makes Akio forget everything about you.")
    async def forget(ctx):
        user_id = str(ctx.author.id)
        if user_id in user_memories:
            del user_memories[user_id]
            save_user_memories()
            await ctx.send("I've forgotten our history together... but I'm excited to get to know you again! (´｡• ᵕ •｡`) ♡", ephemeral=True)
        else:
            await ctx.send("I don't think we've met before, but nice to meet you! (o^▽^o)", ephemeral=True)

    @bot.hybrid_command(name="memory", description="See what Akio remembers about you.")
    async def memory(ctx):
        user_id = str(ctx.author.id)
        if user_id not in user_memories:
            await ctx.send("This is our first time meeting! Hello there! (´｡• ᵕ •｡`) ♡", ephemeral=True)
            return
        
        user_data = user_memories[user_id]
        embed = discord.Embed(title="What I remember about you! ♡", color=0xff69b4)
        
        # Use both display name and username
        display_name = user_data.get("display_name", "Unknown")
        username = user_data.get("username", "Unknown")
        embed.add_field(name="Display Name", value=display_name, inline=True)
        embed.add_field(name="Username", value=f"@{username}", inline=True)
        embed.add_field(name="Times we've talked", value=str(user_data["total_interactions"]), inline=True)
        
        if user_data["interests"]:
            interests = ", ".join(user_data["interests"][:5])  # Show top 5
            embed.add_field(name="Your interests", value=interests, inline=False)
        
        first_met = datetime.fromisoformat(user_data["first_met"])
        embed.add_field(name="First met", value=first_met.strftime("%B %d, %Y"), inline=True)
        
        if "last_interaction" in user_data:
            last_seen = datetime.fromisoformat(user_data["last_interaction"])
            embed.add_field(name="Last talked", value=last_seen.strftime("%B %d, %Y"), inline=True)
        
        embed.set_footer(text="I love getting to know you better! (o^▽^o)")
        await ctx.send(embed=embed, ephemeral=True)

    @bot.hybrid_command(name="memory_stats", description="Show memory usage statistics (Bot owner only).")
    async def memory_stats(ctx):
        # Add a simple check - you can modify this condition as needed
        if ctx.author.id != 603003195911831573:  # Replace with your user ID
            await ctx.send("Only the bot owner can use this command! (￣▽￣)", ephemeral=True)
            return
        
        total_users = len(user_memories)
        total_conversations = sum(len(user_data.get("recent_conversations", [])) for user_data in user_memories.values())
        
        embed = discord.Embed(title="Memory Usage Statistics", color=0x00ff00)
        embed.add_field(name="Total Users Remembered", value=str(total_users), inline=True)
        embed.add_field(name="Total Conversations Stored", value=str(total_conversations), inline=True)
        embed.add_field(name="Memory Limit", value=f"{MEMORY_CLEANUP_THRESHOLD} users", inline=True)
        
        # Estimate memory usage
        import sys
        memory_size = sys.getsizeof(user_memories)
        embed.add_field(name="Estimated Memory", value=f"~{memory_size // 1024}KB", inline=True)
        
        embed.set_footer(text="Memory optimized for hosting efficiency!")
        await ctx.send(embed=embed, ephemeral=True)