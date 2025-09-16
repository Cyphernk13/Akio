import discord
from discord.ext import commands
import aiohttp
import asyncio
import random
import html
import json
import os
from typing import Optional, Dict, List
from datetime import datetime
import logging
import time

# Rate limiting globals
last_api_call = 0
api_call_count = 0
RATE_LIMIT_DELAY = 5  # seconds between API calls
MAX_RETRIES = 3

# Set up logging for trivia module
logging.basicConfig(level=logging.INFO)
trivia_logger = logging.getLogger('trivia')

# Fallback questions for when API fails
FALLBACK_QUESTIONS = [
    {
        "question": "What is the capital of Japan?",
        "correct_answer": "Tokyo",
        "incorrect_answers": ["Osaka", "Kyoto", "Hiroshima"],
        "category": "Geography",
        "difficulty": "easy"
    },
    {
        "question": "What is 2 + 2?",
        "correct_answer": "4",
        "incorrect_answers": ["3", "5", "6"],
        "category": "Mathematics",
        "difficulty": "easy"
    },
    {
        "question": "Who wrote 'Romeo and Juliet'?",
        "correct_answer": "William Shakespeare",
        "incorrect_answers": ["Charles Dickens", "Jane Austen", "Mark Twain"],
        "category": "Literature",
        "difficulty": "easy"
    },
    {
        "question": "What is the largest planet in our solar system?",
        "correct_answer": "Jupiter",
        "incorrect_answers": ["Saturn", "Neptune", "Earth"],
        "category": "Science",
        "difficulty": "easy"
    },
    {
        "question": "In which year did World War II end?",
        "correct_answer": "1945",
        "incorrect_answers": ["1943", "1944", "1946"],
        "category": "History",
        "difficulty": "medium"
    }
]

# Trivia categories mapping
TRIVIA_CATEGORIES = {
    "general": {"id": 9, "name": "General Knowledge"},
    "books": {"id": 10, "name": "Entertainment: Books"},
    "film": {"id": 11, "name": "Entertainment: Film"},
    "music": {"id": 12, "name": "Entertainment: Music"},
    "tv": {"id": 14, "name": "Entertainment: Television"},
    "games": {"id": 15, "name": "Entertainment: Video Games"},
    "science": {"id": 17, "name": "Science & Nature"},
    "computers": {"id": 18, "name": "Science: Computers"},
    "math": {"id": 19, "name": "Science: Mathematics"},
    "mythology": {"id": 20, "name": "Mythology"},
    "sports": {"id": 21, "name": "Sports"},
    "geography": {"id": 22, "name": "Geography"},
    "history": {"id": 23, "name": "History"},
    "politics": {"id": 24, "name": "Politics"},
    "art": {"id": 25, "name": "Art"},
    "celebrities": {"id": 26, "name": "Celebrities"},
    "animals": {"id": 27, "name": "Animals"},
    "vehicles": {"id": 28, "name": "Vehicles"},
    "anime": {"id": 31, "name": "Entertainment: Japanese Anime & Manga"},
    "cartoons": {"id": 32, "name": "Entertainment: Cartoon & Animations"}
}

# Store active trivia sessions
active_sessions = {}

# Question cache for each session
session_question_cache = {}

# Leaderboard data file path
LEADERBOARD_FILE = os.path.join("data", "trivia_leaderboard.json")

class QuestionCache:
    """Cache questions for a trivia session"""
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.questions = []
        self.current_index = 0
        
    def add_questions(self, questions: List[Dict]):
        """Add questions to the cache"""
        self.questions.extend(questions)
        trivia_logger.info(f"Session {self.session_id}: Added {len(questions)} questions to cache. Total: {len(self.questions)}")
    
    def get_next_question(self) -> Optional[Dict]:
        """Get the next question from cache"""
        if self.current_index < len(self.questions):
            question = self.questions[self.current_index]
            self.current_index += 1
            trivia_logger.info(f"Session {self.session_id}: Serving question {self.current_index}/{len(self.questions)} from cache")
            return question
        trivia_logger.warning(f"Session {self.session_id}: No more questions in cache!")
        return None
    
    def has_questions(self) -> bool:
        """Check if cache has more questions"""
        return self.current_index < len(self.questions)
    
    def remaining_questions(self) -> int:
        """Get number of remaining questions"""
        return len(self.questions) - self.current_index

def load_leaderboard() -> dict:
    """Load leaderboard data from JSON file"""
    try:
        os.makedirs("data", exist_ok=True)
        if os.path.exists(LEADERBOARD_FILE):
            with open(LEADERBOARD_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading leaderboard: {e}")
    return {}

def save_leaderboard(data: dict):
    """Save leaderboard data to JSON file"""
    try:
        os.makedirs("data", exist_ok=True)
        with open(LEADERBOARD_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving leaderboard: {e}")

def update_user_stats(user_id: int, username: str, is_correct: bool, difficulty: str, is_skipped: bool = False) -> dict:
    """Update user statistics in the leaderboard"""
    leaderboard_data = load_leaderboard()
    user_id_str = str(user_id)
    
    if user_id_str not in leaderboard_data:
        leaderboard_data[user_id_str] = {
            "user_id": user_id_str,
            "username": username,
            "total_points": 0,
            "questions_answered": 0,
            "correct_answers": 0,
            "skipped_questions": 0,
            "best_streak": 0,
            "current_streak": 0,
            "easy_correct": 0,
            "medium_correct": 0,
            "hard_correct": 0,
            "first_played": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    user_stats = leaderboard_data[user_id_str]
    user_stats["username"] = username  # Update username in case it changed
    
    # Ensure all keys exist (for backwards compatibility)
    if "skipped_questions" not in user_stats:
        user_stats["skipped_questions"] = 0
    if "current_streak" not in user_stats:
        user_stats["current_streak"] = 0
    if "best_streak" not in user_stats:
        user_stats["best_streak"] = 0
    
    if not is_skipped:
        user_stats["questions_answered"] += 1
        
        if is_correct:
            user_stats["correct_answers"] += 1
            user_stats["current_streak"] += 1
            
            # Add points based on difficulty
            points = {"easy": 1, "medium": 2, "hard": 3}
            user_stats["total_points"] += points[difficulty]
            
            # Update difficulty-specific stats
            user_stats[f"{difficulty}_correct"] += 1
            
            # Update best streak
            if user_stats["current_streak"] > user_stats["best_streak"]:
                user_stats["best_streak"] = user_stats["current_streak"]
        else:
            user_stats["current_streak"] = 0
    else:
        user_stats["skipped_questions"] += 1
        user_stats["current_streak"] = 0
    
    save_leaderboard(leaderboard_data)
    return user_stats

async def fetch_questions_batch(category_id: int, difficulty: str, session_token: str = None, amount: int = 50) -> List[Dict]:
    """Fetch a batch of questions to populate cache with rate limiting"""
    global last_api_call, api_call_count
    
    # Rate limiting
    current_time = time.time()
    if current_time - last_api_call < RATE_LIMIT_DELAY:
        sleep_time = RATE_LIMIT_DELAY - (current_time - last_api_call)
        trivia_logger.info(f"Rate limiting: sleeping for {sleep_time:.1f}s")
        await asyncio.sleep(sleep_time)
    
    trivia_logger.info(f"Fetching batch of {amount} questions for category {category_id}, difficulty {difficulty}")
    
    url = "https://opentdb.com/api.php"
    params = {
        "amount": amount,
        "category": category_id,
        "difficulty": difficulty
    }
    
    if session_token:
        params["token"] = session_token
    
    last_api_call = time.time()
    api_call_count += 1
    
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.get(url, params=params) as response:
                trivia_logger.info(f"Batch API Request: {response.url}")
                trivia_logger.info(f"Batch API Status: {response.status}")
                
                if response.status == 429:
                    trivia_logger.warning(f"Rate limited (429), waiting 30 seconds...")
                    await asyncio.sleep(30)
                    return []
                
                if response.status != 200:
                    trivia_logger.error(f"HTTP Error: {response.status}")
                    return []
                
                data = await response.json()
                trivia_logger.info(f"Batch API Response Code: {data.get('response_code')}")
                trivia_logger.info(f"Batch API Results Count: {len(data.get('results', []))}")
                
                # Check response code
                if data.get("response_code") == 0 and data.get("results"):
                    questions = data["results"]
                    trivia_logger.info(f"Successfully fetched {len(questions)} questions")
                    return questions
                elif data.get("response_code") == 4:  # Token exhausted
                    trivia_logger.warning("Session token exhausted during batch fetch, trying without token")
                    return []  # Don't recursively call, let populate_question_cache handle it
                elif data.get("response_code") == 1:  # No results
                    trivia_logger.warning(f"No results for batch fetch - category {category_id}, difficulty {difficulty}")
                    return []  # Let populate_question_cache try mixed difficulties
                else:
                    trivia_logger.warning(f"API returned response code: {data.get('response_code')}")
                    return []
                    
    except asyncio.TimeoutError:
        trivia_logger.error("Timeout during batch fetch")
        return []
    except Exception as e:
        trivia_logger.error(f"Exception during batch fetch: {e}")
        return []

def decode_text(text: str) -> str:
    """Decode HTML entities"""
    return html.unescape(text)

async def safe_interaction_response(interaction: discord.Interaction, content: str = None, embed: discord.Embed = None, view: discord.ui.View = None, ephemeral: bool = False):
    """Safely handle interaction responses with timeout protection"""
    try:
        if interaction.response.is_done():
            # If response is already sent, try to edit or follow up
            if content or embed:
                try:
                    await interaction.edit_original_response(content=content, embed=embed, view=view)
                except:
                    await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=ephemeral)
        else:
            # Send initial response
            await interaction.response.send_message(content=content, embed=embed, view=view, ephemeral=ephemeral)
    except discord.errors.NotFound:
        trivia_logger.warning("Interaction expired - could not respond")
    except discord.errors.InteractionResponded:
        trivia_logger.warning("Interaction already responded to")
    except Exception as e:
        trivia_logger.error(f"Error in interaction response: {e}")

async def safe_interaction_edit(interaction: discord.Interaction, content: str = None, embed: discord.Embed = None, view: discord.ui.View = None):
    """Safely edit interaction responses"""
    try:
        await interaction.response.edit_message(content=content, embed=embed, view=view)
    except discord.errors.NotFound:
        trivia_logger.warning("Interaction expired - could not edit")
    except Exception as e:
        trivia_logger.error(f"Error editing interaction: {e}")

class TriviaSession:
    """Class to manage ongoing trivia sessions"""
    def __init__(self, user_id: int, category: int, difficulty: str, session_token: str = None):
        self.user_id = user_id
        self.category = category
        self.current_difficulty = difficulty
        self.session_token = session_token
        self.questions_answered = 0
        self.correct_answers = 0
        self.skipped_questions = 0
        self.current_streak = 0
        self.session_points = 0
        self.active = True
        self.max_questions = 50
        self.token_reset_attempts = 0  # Track token reset attempts
        self.fallback_mode = False  # Track if we're in fallback mode (no token)
        self.session_id = f"{user_id}_{category}_{datetime.now().timestamp()}"
        self.cache_populated = False
        trivia_logger.info(f"Created new session: {self.session_id}")
        
    def get_cache(self) -> Optional[QuestionCache]:
        """Get the question cache for this session"""
        return session_question_cache.get(self.session_id)
        
    def create_cache(self) -> QuestionCache:
        """Create a new question cache for this session"""
        cache = QuestionCache(self.session_id)
        session_question_cache[self.session_id] = cache
        return cache
        
    def cleanup_cache(self):
        """Clean up the question cache when session ends"""
        if self.session_id in session_question_cache:
            del session_question_cache[self.session_id]
            trivia_logger.info(f"Cleaned up cache for session: {self.session_id}")

async def populate_question_cache(session: TriviaSession) -> bool:
    """Populate the question cache for a session with better error handling"""
    trivia_logger.info(f"Populating cache for session {session.session_id}")
    
    cache = session.create_cache()
    
    # Try to fetch 25 questions initially (reduced from 50 to avoid rate limits)
    questions = await fetch_questions_batch(session.category, session.current_difficulty, session.session_token, 25)
    
    if questions:
        cache.add_questions(questions)
        session.cache_populated = True
        trivia_logger.info(f"Cache populated with {len(questions)} questions")
        return True
    
    # If failed, try without session token
    trivia_logger.warning("Batch fetch failed with token, trying without token")
    await asyncio.sleep(2)  # Brief delay before retry
    questions = await fetch_questions_batch(session.category, session.current_difficulty, None, 25)
    
    if questions:
        cache.add_questions(questions)
        session.cache_populated = True
        session.fallback_mode = True
        trivia_logger.info(f"Cache populated with {len(questions)} questions (fallback mode)")
        return True
    
    # If still failed, try mixed difficulties with smaller batches
    trivia_logger.warning("Trying mixed difficulties for cache population")
    for difficulty in ["easy", "medium", "hard"]:
        await asyncio.sleep(1)  # Rate limiting between attempts
        questions = await fetch_questions_batch(session.category, difficulty, None, 10)
        if questions:
            # Mark questions with their actual difficulty
            for q in questions:
                q["actual_difficulty"] = difficulty
            cache.add_questions(questions)
    
    if cache.questions:
        session.cache_populated = True
        session.fallback_mode = True
        trivia_logger.info(f"Cache populated with {len(cache.questions)} mixed difficulty questions")
        return True
    
    # Final fallback - use hardcoded questions
    trivia_logger.warning("Using fallback questions - API completely unavailable")
    fallback_questions = random.sample(FALLBACK_QUESTIONS, min(5, len(FALLBACK_QUESTIONS)))
    for q in fallback_questions:
        q["actual_difficulty"] = q["difficulty"]
    cache.add_questions(fallback_questions)
    session.cache_populated = True
    session.fallback_mode = True
    trivia_logger.info(f"Cache populated with {len(fallback_questions)} fallback questions")
    return True

async def fetch_trivia_question(category_id: int, difficulty: str, session_token: str = None, question_type: str = None, _recursion_depth: int = 0) -> Optional[Dict]:
    """Fetch trivia question with fallback strategies"""
    # Prevent infinite recursion
    if _recursion_depth > 3:
        print(f"Max recursion depth reached, returning None")
        return None
        
    url = "https://opentdb.com/api.php"
    params = {
        "amount": 1,
        "category": category_id,
        "difficulty": difficulty
    }
    
    # Mix of multiple choice and boolean questions for variety
    if question_type:
        params["type"] = question_type
    
    if session_token:
        params["token"] = session_token
    
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(url, params=params) as response:
                print(f"API Request: {response.url}")
                print(f"Status: {response.status}")
                
                if response.status != 200:
                    print(f"HTTP Error: {response.status}")
                    return None
                
                data = await response.json()
                print(f"Response: {data}")
                
                # Check response code
                if data.get("response_code") == 0 and data.get("results"):
                    return data["results"][0]
                elif data.get("response_code") == 4:  # Token exhausted
                    print("Session token exhausted, trying without token")
                    return await fetch_trivia_question(category_id, difficulty, None, question_type, _recursion_depth + 1)
                elif data.get("response_code") == 1:  # No results
                    print(f"No results for {difficulty} in category {category_id}, trying different approaches")
                    # First try without session token for same difficulty
                    if session_token and _recursion_depth == 0:
                        print("Trying same difficulty without session token")
                        result = await fetch_trivia_question(category_id, difficulty, None, question_type, _recursion_depth + 1)
                        if result:
                            return result
                    
                    # Then try different question types for same difficulty
                    if question_type and _recursion_depth <= 1:
                        print("Trying different question type")
                        result = await fetch_trivia_question(category_id, difficulty, session_token, None, _recursion_depth + 1)
                        if result:
                            return result
                    
                    # Finally try different difficulties as fallback
                    if _recursion_depth <= 2:
                        for fallback_diff in ["medium", "easy", "hard"]:
                            if fallback_diff != difficulty:
                                print(f"Trying fallback difficulty: {fallback_diff}")
                                result = await fetch_trivia_question(category_id, fallback_diff, None, None, _recursion_depth + 1)
                                if result:
                                    result["original_difficulty"] = difficulty
                                    result["actual_difficulty"] = fallback_diff
                                    return result
                    return None
                else:
                    print(f"API Error Code: {data.get('response_code')}")
                    return None
    
    except Exception as e:
        print(f"Exception fetching question: {e}")
        return None

async def get_session_token() -> Optional[str]:
    """Get a session token from the trivia API with retry logic"""
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get("https://opentdb.com/api_token.php?command=request") as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("response_code") == 0:
                            print(f"Session token obtained: {data.get('token')[:10]}...")
                            return data.get("token")
                    print(f"Token request failed, attempt {attempt + 1}")
        except Exception as e:
            print(f"Error getting session token (attempt {attempt + 1}): {e}")
        
        if attempt < 2:
            await asyncio.sleep(1)
    
    print("Failed to get session token after 3 attempts")
    return None

async def reset_session_token(token: str) -> bool:
    """Reset a session token when exhausted"""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            url = f"https://opentdb.com/api_token.php?command=reset&token={token}"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("response_code") == 0
    except Exception as e:
        print(f"Error resetting session token: {e}")
    return False

async def next_question_callback(interaction: discord.Interaction, session: TriviaSession):
    """Callback for getting the next question"""
    trivia_logger.info(f"Next question requested for session {session.session_id}")
    
    try:
        # Check if we've reached max questions
        if session.questions_answered >= session.max_questions:
            trivia_logger.info(f"Session {session.session_id} reached max questions")
            await end_session(interaction, session, "Maximum questions reached!")
            return
        
        # Get question from cache
        cache = session.get_cache()
        question_data = None
        
        if cache and cache.has_questions():
            question_data = cache.get_next_question()
            trivia_logger.info(f"Session {session.session_id}: Got question from cache. Remaining: {cache.remaining_questions()}")
        else:
            trivia_logger.warning(f"Session {session.session_id}: Cache empty or missing, trying to fetch new questions")
            
            # Try to repopulate cache if it's empty
            if not cache:
                cache = session.create_cache()
            
            # Fetch more questions
            new_questions = await fetch_questions_batch(
                session.category, 
                session.current_difficulty, 
                session.session_token if not session.fallback_mode else None, 
                25
            )
            
            if new_questions:
                cache.add_questions(new_questions)
                question_data = cache.get_next_question()
                trivia_logger.info(f"Session {session.session_id}: Repopulated cache and got question")
            else:
                trivia_logger.error(f"Session {session.session_id}: Failed to fetch new questions")
        
        if not question_data:
            trivia_logger.error(f"Session {session.session_id}: No question data available, ending session")
            await end_session(interaction, session, "Unable to fetch more questions. Thanks for playing!")
            return
        
        # Create new question view
        question_view = TriviaQuestionView(question_data, session, next_question_callback)
        embed = question_view.create_question_embed()
        
        await interaction.response.edit_message(embed=embed, view=question_view)
        trivia_logger.info(f"Session {session.session_id}: Successfully displayed next question")
        
    except Exception as e:
        trivia_logger.error(f"Error in next_question_callback for session {session.session_id}: {e}")
        await interaction.response.send_message(
            "❌ An error occurred while fetching the next question.",
            ephemeral=True
        )

async def end_session(interaction: discord.Interaction, session: TriviaSession, reason: str = "Session ended"):
    """Helper function to end a trivia session"""
    trivia_logger.info(f"Ending session {session.session_id}: {reason}")
    trivia_logger.info(f"Session stats at end - Questions: {session.questions_answered}, Correct: {session.correct_answers}, Skipped: {session.skipped_questions}")
    
    session.active = False
    if session.user_id in active_sessions:
        del active_sessions[session.user_id]
        trivia_logger.info(f"Removed session {session.session_id} from active_sessions")
    
    # Clean up the question cache
    session.cleanup_cache()
    
    # Create final summary embed
    accuracy = (session.correct_answers / max(session.questions_answered, 1)) * 100 if session.questions_answered > 0 else 0
    
    embed = discord.Embed(
        title="🎯 Trivia Session Complete!",
        description=f"{reason}\n\nHere's your final summary:",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="📊 Final Results",
        value=f"Questions: {session.questions_answered}\nCorrect: {session.correct_answers}\nSkipped: {session.skipped_questions}\nAccuracy: {accuracy:.1f}%\nPoints: {session.session_points}",
        inline=False
    )
    
    # Disable all buttons
    view = discord.ui.View()
    for item in view.children:
        item.disabled = True
    
    await interaction.response.edit_message(embed=embed, view=view)

class DifficultySelect(discord.ui.View):
    """View for selecting trivia difficulty"""
    def __init__(self, category_id: int, user_id: int):
        super().__init__(timeout=60.0)
        self.category_id = category_id
        self.user_id = user_id
    
    @discord.ui.button(label='🟢 Easy', style=discord.ButtonStyle.green)
    async def easy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This trivia session is not for you!", ephemeral=True)
            return
        await self.start_trivia_session(interaction, 'easy')
    
    @discord.ui.button(label='🟡 Medium', style=discord.ButtonStyle.primary)
    async def medium_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This trivia session is not for you!", ephemeral=True)
            return
        await self.start_trivia_session(interaction, 'medium')
    
    @discord.ui.button(label='🔴 Hard', style=discord.ButtonStyle.danger)
    async def hard_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This trivia session is not for you!", ephemeral=True)
            return
        await self.start_trivia_session(interaction, 'hard')
    
    async def start_trivia_session(self, interaction: discord.Interaction, difficulty: str):
        """Start a new trivia session"""
        trivia_logger.info(f"Starting trivia session for user {self.user_id}, category {self.category_id}, difficulty {difficulty}")
        
        # Check if user already has an active session
        if self.user_id in active_sessions:
            await interaction.response.send_message("❌ You already have an active trivia session! Please finish it first.", ephemeral=True)
            return
        
        # Get session token
        session_token = await get_session_token()
        trivia_logger.info(f"Session token obtained: {session_token[:10] if session_token else 'None'}...")
        
        # Create new session
        session = TriviaSession(
            user_id=self.user_id,
            category=self.category_id,
            difficulty=difficulty,
            session_token=session_token
        )
        
        # Store active session
        active_sessions[self.user_id] = session
        
        # Populate question cache
        trivia_logger.info(f"Populating cache for session {session.session_id}")
        cache_success = await populate_question_cache(session)
        
        if not cache_success:
            trivia_logger.error(f"Failed to populate cache for session {session.session_id}")
            await interaction.response.send_message(
                "❌ Failed to fetch trivia questions. Please try again later or choose a different category.",
                ephemeral=True
            )
            # Remove the session since it failed
            if self.user_id in active_sessions:
                del active_sessions[self.user_id]
            session.cleanup_cache()
            return
        
        # Get first question from cache
        cache = session.get_cache()
        question_data = cache.get_next_question()
        
        if not question_data:
            trivia_logger.error(f"No question data available from cache for session {session.session_id}")
            await interaction.response.send_message(
                "❌ Failed to get trivia question. Please try again later or choose a different category.",
                ephemeral=True
            )
            # Remove the session since it failed
            if self.user_id in active_sessions:
                del active_sessions[self.user_id]
            session.cleanup_cache()
            return
        
        trivia_logger.info(f"Session {session.session_id} started successfully with {cache.remaining_questions()} questions in cache")
        
        # Create question view
        question_view = TriviaQuestionView(question_data, session, next_question_callback)
        embed = question_view.create_question_embed()
        
        await interaction.response.edit_message(embed=embed, view=question_view)

class TriviaQuestionView(discord.ui.View):
    """View for answering trivia questions with skip option"""
    def __init__(self, question_data: Dict, session: TriviaSession, next_question_callback):
        super().__init__(timeout=60.0)
        self.question_data = question_data
        self.session = session
        self.next_question_callback = next_question_callback
        self.answered = False
        
        # Decode all text
        self.question = decode_text(question_data["question"])
        self.correct_answer = decode_text(question_data["correct_answer"])
        self.category = decode_text(question_data["category"])
        
        # Check if this question had difficulty adjusted
        self.actual_difficulty = question_data.get("actual_difficulty", session.current_difficulty)
        
        # Handle answers based on question type
        if question_data["type"] == "boolean":
            self.setup_boolean_buttons()
        else:
            self.setup_multiple_choice_buttons()
        
        # Add skip button
        self.add_skip_button()
    
    def setup_boolean_buttons(self):
        """Setup True/False buttons"""
        true_button = discord.ui.Button(label='True', style=discord.ButtonStyle.green, emoji='✅')
        false_button = discord.ui.Button(label='False', style=discord.ButtonStyle.red, emoji='❌')
        
        true_button.callback = lambda i: self.answer_callback(i, 'True')
        false_button.callback = lambda i: self.answer_callback(i, 'False')
        
        self.add_item(true_button)
        self.add_item(false_button)
    
    def setup_multiple_choice_buttons(self):
        """Setup multiple choice buttons"""
        # Combine correct and incorrect answers
        all_answers = [self.correct_answer] + [decode_text(ans) for ans in self.question_data["incorrect_answers"]]
        random.shuffle(all_answers)
        
        # Create buttons for each answer (max 4)
        emojis = ['🇦', '🇧', '🇨', '🇩']
        for i, answer in enumerate(all_answers[:4]):
            button = discord.ui.Button(
                label=f"{answer[:75]}{'...' if len(answer) > 75 else ''}", 
                style=discord.ButtonStyle.secondary, 
                emoji=emojis[i]
            )
            button.callback = lambda interaction, ans=answer: self.answer_callback(interaction, ans)
            self.add_item(button)
    
    def add_skip_button(self):
        """Add skip button"""
        skip_button = discord.ui.Button(label='Skip', style=discord.ButtonStyle.secondary, emoji='⏭️')
        skip_button.callback = self.skip_question
        self.add_item(skip_button)
    
    async def answer_callback(self, interaction: discord.Interaction, answer: str):
        """Handle answer selection"""
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message("This trivia question is not for you!", ephemeral=True)
            return
        
        if self.answered:
            await interaction.response.send_message("You already answered this question!", ephemeral=True)
            return
        
        self.answered = True
        
        # Check if answer is correct
        is_correct = answer.lower().strip() == self.correct_answer.lower().strip()
        
        # Update session stats
        self.session.questions_answered += 1
        if is_correct:
            self.session.correct_answers += 1
            self.session.current_streak += 1
            # Use actual difficulty for points
            points = {"easy": 1, "medium": 2, "hard": 3}
            self.session.session_points += points[self.actual_difficulty]
        else:
            self.session.current_streak = 0
        
        # Update global leaderboard
        user_stats = update_user_stats(
            self.session.user_id, 
            interaction.user.display_name, 
            is_correct, 
            self.actual_difficulty
        )
        
        # Create result embed
        embed = self.create_result_embed(answer, is_correct, user_stats)
        
        # Create next question view with change difficulty and stop buttons
        next_view = NextQuestionView(self.session, self.next_question_callback, interaction)
        
        await interaction.response.edit_message(embed=embed, view=next_view)
    
    async def skip_question(self, interaction: discord.Interaction):
        """Handle skip question button"""
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message("This trivia question is not for you!", ephemeral=True)
            return
        
        if self.answered:
            await interaction.response.send_message("You already answered this question!", ephemeral=True)
            return
        
        self.answered = True
        
        # Update session stats for skip
        self.session.skipped_questions += 1
        self.session.current_streak = 0
        
        # Update global leaderboard with error handling
        try:
            user_stats = update_user_stats(
                self.session.user_id, 
                interaction.user.display_name, 
                False, 
                self.actual_difficulty,
                is_skipped=True
            )
        except Exception as e:
            trivia_logger.error(f"Error updating user stats for skip: {e}")
            # Use session stats as fallback
            user_stats = {
                "current_streak": self.session.current_streak,
                "total_points": self.session.session_points,
                "questions_answered": self.session.questions_answered,
                "correct_answers": self.session.correct_answers,
                "skipped_questions": self.session.skipped_questions
            }
        
        # Create skip result embed
        embed = self.create_skip_embed(user_stats)
        
        # Create next question view
        next_view = NextQuestionView(self.session, self.next_question_callback, interaction)
        
        await interaction.response.edit_message(embed=embed, view=next_view)
    
    def create_question_embed(self) -> discord.Embed:
        """Create embed for the trivia question"""
        difficulty_colors = {
            'easy': discord.Color.green(),
            'medium': discord.Color.orange(),
            'hard': discord.Color.red()
        }
        
        difficulty_emojis = {
            'easy': '🟢',
            'medium': '🟡', 
            'hard': '🔴'
        }
        
        embed = discord.Embed(
            title=f"{difficulty_emojis[self.actual_difficulty]} Trivia Question #{self.session.questions_answered + 1}",
            description=f"**{self.question}**",
            color=difficulty_colors[self.actual_difficulty]
        )
        
        embed.add_field(
            name="📚 Category", 
            value=self.category, 
            inline=True
        )
        embed.add_field(
            name="⚡ Difficulty", 
            value=self.actual_difficulty.title(), 
            inline=True
        )
        embed.add_field(
            name="🔥 Current Streak", 
            value=str(self.session.current_streak), 
            inline=True
        )
        
        embed.add_field(
            name="📊 Session Stats",
            value=f"Correct: {self.session.correct_answers}/{self.session.questions_answered} | Skipped: {self.session.skipped_questions} | Points: {self.session.session_points}",
            inline=False
        )
        
        # Add cache info if available
        cache = self.session.get_cache()
        if cache:
            embed.add_field(
                name="💾 Cache Info",
                value=f"Questions remaining: {cache.remaining_questions()}",
                inline=True
            )
        
        # Add fallback mode indicator if active
        footer_text = "You have 60 seconds to answer! Use ⏭️ to skip."
        if self.session.fallback_mode:
            footer_text += " ⚠️ Running in extended mode (no duplicates filtering)"
        
        embed.set_footer(text=footer_text)
        return embed
    
    def create_result_embed(self, user_answer: str, is_correct: bool, user_stats: dict) -> discord.Embed:
        """Create embed showing the result"""
        if is_correct:
            embed = discord.Embed(
                title="✅ Correct!",
                description=f"**{self.question}**",
                color=discord.Color.green()
            )
            embed.add_field(
                name="🎉 Your Answer",
                value=user_answer,
                inline=False
            )
        else:
            embed = discord.Embed(
                title="❌ Incorrect!",
                description=f"**{self.question}**",
                color=discord.Color.red()
            )
            embed.add_field(
                name="❌ Your Answer",
                value=user_answer,
                inline=True
            )
            embed.add_field(
                name="✅ Correct Answer",
                value=self.correct_answer,
                inline=True
            )
        
        embed.add_field(
            name="📊 Session Stats",
            value=f"Questions: {self.session.questions_answered} | Correct: {self.session.correct_answers} | Skipped: {self.session.skipped_questions} | Points: {self.session.session_points} | Streak: {self.session.current_streak}",
            inline=False
        )
        
        embed.add_field(
            name="🏆 Overall Stats",
            value=f"Total Points: {user_stats['total_points']} | Accuracy: {(user_stats['correct_answers']/max(user_stats['questions_answered'], 1)*100):.1f}% | Best Streak: {user_stats['best_streak']}",
            inline=False
        )
        
        return embed
    
    def create_skip_embed(self, user_stats: dict) -> discord.Embed:
        """Create embed for skipped question"""
        embed = discord.Embed(
            title="⏭️ Question Skipped",
            description=f"**{self.question}**",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="✅ Correct Answer",
            value=self.correct_answer,
            inline=False
        )
        
        embed.add_field(
            name="📊 Session Stats",
            value=f"Questions: {self.session.questions_answered} | Correct: {self.session.correct_answers} | Skipped: {self.session.skipped_questions} | Points: {self.session.session_points}",
            inline=False
        )
        
        return embed
    
    async def on_timeout(self):
        """Handle timeout - treat as skip"""
        if not self.answered and self.session.active:
            trivia_logger.info(f"Question timed out for session {self.session.session_id} - treating as skip")
            self.session.skipped_questions += 1
            self.session.current_streak = 0
            
            # Update stats for timeout (counts as skip)
            update_user_stats(
                self.session.user_id, 
                "Unknown User", 
                False, 
                self.actual_difficulty,
                is_skipped=True
            )
            
            for item in self.children:
                item.disabled = True
            
            embed = discord.Embed(
                title="⏰ Time's Up!",
                description=f"**{self.question}**",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="✅ Correct Answer",
                value=self.correct_answer,
                inline=False
            )
            
            # Create next question view
            next_view = NextQuestionView(self.session, self.next_question_callback, None)
            
            try:
                await self.message.edit(embed=embed, view=next_view)
            except:
                pass

class NextQuestionView(discord.ui.View):
    """View for continuing to next question with difficulty change and stop options"""
    def __init__(self, session: TriviaSession, next_question_callback, interaction):
        super().__init__(timeout=30.0)
        self.session = session
        self.next_question_callback = next_question_callback
        self.interaction = interaction
    
    @discord.ui.button(label='Next Question', style=discord.ButtonStyle.primary, emoji='➡️')
    async def next_question(self, interaction: discord.Interaction, button: discord.ui.Button):
        trivia_logger.info(f"Next question button clicked for session {self.session.session_id}")
        trivia_logger.info(f"Session active status: {self.session.active}")
        
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message("This trivia session is not for you!", ephemeral=True)
            return
        
        if not self.session.active:
            trivia_logger.warning(f"Next question clicked but session {self.session.session_id} is not active")
            await interaction.response.send_message("This trivia session has ended!", ephemeral=True)
            return
        
        await self.next_question_callback(interaction, self.session)
    
    @discord.ui.button(label='Change Difficulty', style=discord.ButtonStyle.secondary, emoji='🔄')
    async def change_difficulty(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message("This trivia session is not for you!", ephemeral=True)
            return
        
        if not self.session.active:
            await interaction.response.send_message("This trivia session has ended!", ephemeral=True)
            return
        
        # Create difficulty selection view
        view = ChangeDifficultyView(self.session, self.next_question_callback)
        
        embed = discord.Embed(
            title="🔄 Change Difficulty",
            description=f"Current difficulty: **{self.session.current_difficulty.title()}**\n\nSelect new difficulty:",
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="🟢 Easy",
            value="Basic questions (1 point each)",
            inline=True
        )
        embed.add_field(
            name="🟡 Medium", 
            value="Moderate questions (2 points each)",
            inline=True
        )
        embed.add_field(
            name="🔴 Hard",
            value="Challenging questions (3 points each)",
            inline=True
        )
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label='Stop Trivia', style=discord.ButtonStyle.danger, emoji='🛑')
    async def stop_trivia(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message("This trivia session is not for you!", ephemeral=True)
            return
        
        await end_session(interaction, self.session, "You chose to end the session.")
    
    async def on_timeout(self):
        # Just disable the buttons, but don't end the session
        for item in self.children:
            item.disabled = True

class ChangeDifficultyView(discord.ui.View):
    """View for changing difficulty mid-session"""
    def __init__(self, session: TriviaSession, next_question_callback):
        super().__init__(timeout=30.0)
        self.session = session
        self.next_question_callback = next_question_callback
    
    @discord.ui.button(label='🟢 Easy', style=discord.ButtonStyle.green)
    async def easy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.change_difficulty(interaction, 'easy')
    
    @discord.ui.button(label='🟡 Medium', style=discord.ButtonStyle.primary)
    async def medium_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.change_difficulty(interaction, 'medium')
    
    @discord.ui.button(label='🔴 Hard', style=discord.ButtonStyle.danger)
    async def hard_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.change_difficulty(interaction, 'hard')
    
    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.secondary, emoji='❌')
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Go back to next question view
        next_view = NextQuestionView(self.session, self.next_question_callback, interaction)
        
        embed = discord.Embed(
            title="🎯 Ready for Next Question?",
            description="Choose your next action:",
            color=discord.Color.blue()
        )
        
        await interaction.response.edit_message(embed=embed, view=next_view)
    
    async def change_difficulty(self, interaction: discord.Interaction, new_difficulty: str):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message("This trivia session is not for you!", ephemeral=True)
            return
        
        old_difficulty = self.session.current_difficulty
        self.session.current_difficulty = new_difficulty
        
        embed = discord.Embed(
            title="✅ Difficulty Changed!",
            description=f"Changed from **{old_difficulty.title()}** to **{new_difficulty.title()}**",
            color=discord.Color.green()
        )
        
        # Create next question view
        next_view = NextQuestionView(self.session, self.next_question_callback, interaction)
        
        await interaction.response.edit_message(embed=embed, view=next_view)

@commands.hybrid_command(
    name="trivia", 
    aliases=["tr"],
    description="Start a trivia game with skip and difficulty change options!"
)
async def trivia(ctx, category: str = None):
    """
    Start a trivia game with the specified category.
    
    Available categories:
    general, books, film, music, tv, games, science, computers, math, 
    mythology, sports, geography, history, politics, art, celebrities, 
    animals, vehicles, anime, cartoons
    """
    
    # Clean up any stuck sessions for this user
    user_id = ctx.author.id
    if user_id in active_sessions:
        old_session = active_sessions[user_id]
        if not old_session.active:
            trivia_logger.info(f"Cleaning up inactive session for user {user_id}")
            old_session.cleanup_cache()
            del active_sessions[user_id]
    
    if not category:
        # Show available categories
        embed = discord.Embed(
            title="🧠 Trivia Categories",
            description="Choose a category to start your trivia game!",
            color=discord.Color.blue()
        )
        
        categories_text = ""
        for key, value in TRIVIA_CATEGORIES.items():
            categories_text += f"`{key}` - {value['name']}\n"
        
        embed.add_field(
            name="📚 Available Categories",
            value=categories_text,
            inline=False
        )
        
        embed.add_field(
            name="💡 Usage",
            value="`akio trivia <category>` or `/trivia <category>`\nExample: `akio trivia anime`",
            inline=False
        )
        
        embed.set_footer(text="Pick a category and test your knowledge!")
        await ctx.send(embed=embed)
        return
    
    # Validate category
    if category.lower() not in TRIVIA_CATEGORIES:
        embed = discord.Embed(
            title="❌ Invalid Category",
            description=f"'{category}' is not a valid category.",
            color=discord.Color.red()
        )
        embed.add_field(
            name="📚 Available Categories",
            value=", ".join(f"`{key}`" for key in TRIVIA_CATEGORIES.keys()),
            inline=False
        )
        await ctx.send(embed=embed)
        return
    
    category = category.lower()
    category_info = TRIVIA_CATEGORIES[category]
    category_name = category_info["name"]
    category_id = category_info["id"]
    
    # Create difficulty selection embed
    embed = discord.Embed(
        title="🎯 Select Difficulty",
        description=f"**Category:** {category_name}\n\nChoose your difficulty level:",
        color=discord.Color.purple()
    )
    
    embed.add_field(
        name="🟢 Easy",
        value="Basic questions (1 point each)",
        inline=True
    )
    embed.add_field(
        name="🟡 Medium", 
        value="Moderate questions (2 points each)",
        inline=True
    )
    embed.add_field(
        name="🔴 Hard",
        value="Challenging questions (3 points each)",
        inline=True
    )
    
    embed.set_footer(text="✨ You can change difficulty during the game!")
    
    view = DifficultySelect(category_id, ctx.author.id)
    await ctx.send(embed=embed, view=view)

@commands.hybrid_command(name="stats", description="View your trivia statistics")
async def trivia_stats(ctx, member: discord.Member = None):
    """View trivia statistics for yourself or another user"""
    target_user = member or ctx.author
    user_id = str(target_user.id)
    
    leaderboard_data = load_leaderboard()
    
    if user_id not in leaderboard_data:
        await ctx.send(f"❌ {target_user.display_name} hasn't played trivia yet!")
        return
    
    stats = leaderboard_data[user_id]
    
    # Calculate accuracy
    total_answered = stats['questions_answered']
    accuracy = (stats['correct_answers'] / max(total_answered, 1)) * 100 if total_answered > 0 else 0
    
    # Calculate average points per question
    avg_points = stats['total_points'] / max(total_answered, 1) if total_answered > 0 else 0
    
    embed = discord.Embed(
        title=f"🎯 Trivia Stats for {stats['username']}",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="📊 Overall Performance",
        value=f"Questions Answered: {total_answered}\nCorrect Answers: {stats['correct_answers']}\nSkipped Questions: {stats.get('skipped_questions', 0)}\nAccuracy: {accuracy:.1f}%\nTotal Points: {stats['total_points']}",
        inline=True
    )
    
    embed.add_field(
        name="🏆 Records",
        value=f"Best Streak: {stats['best_streak']}\nAvg Points/Question: {avg_points:.1f}\nEasy Correct: {stats['easy_correct']}\nMedium Correct: {stats['medium_correct']}\nHard Correct: {stats['hard_correct']}",
        inline=True
    )
    
    # Rank calculation
    sorted_users = sorted(leaderboard_data.values(), key=lambda x: x['total_points'], reverse=True)
    rank = next((i+1 for i, user in enumerate(sorted_users) if user['user_id'] == user_id), "N/A")
    
    embed.add_field(
        name="🥇 Ranking",
        value=f"Global Rank: #{rank} out of {len(leaderboard_data)} players",
        inline=False
    )
    
    embed.set_thumbnail(url=target_user.display_avatar.url)
    embed.set_footer(text=f"First played: {stats['first_played']}")
    
    await ctx.send(embed=embed)

@commands.hybrid_command(name="leaderboard", aliases=["lead"], description="View the trivia leaderboard")
async def trivia_leaderboard(ctx, page: int = 1):
    """View the trivia leaderboard"""
    leaderboard_data = load_leaderboard()
    
    if not leaderboard_data:
        await ctx.send("❌ No trivia stats available yet! Play some trivia to get on the leaderboard.")
        return
    
    # Sort users by total points
    sorted_users = sorted(leaderboard_data.values(), key=lambda x: x['total_points'], reverse=True)
    
    # Pagination
    users_per_page = 10
    total_pages = (len(sorted_users) + users_per_page - 1) // users_per_page
    page = max(1, min(page, total_pages))
    
    start_idx = (page - 1) * users_per_page
    end_idx = start_idx + users_per_page
    page_users = sorted_users[start_idx:end_idx]
    
    embed = discord.Embed(
        title="🏆 Trivia Leaderboard",
        description=f"Top trivia players (Page {page}/{total_pages})",
        color=discord.Color.gold()
    )
    
    leaderboard_text = ""
    for i, user_stats in enumerate(page_users, start=start_idx + 1):
        total_answered = user_stats['questions_answered']
        accuracy = (user_stats['correct_answers'] / max(total_answered, 1)) * 100 if total_answered > 0 else 0
        
        # Medal emojis for top 3
        if i == 1:
            medal = "🥇"
        elif i == 2:
            medal = "🥈"
        elif i == 3:
            medal = "🥉"
        else:
            medal = f"**{i}.**"
        
        leaderboard_text += f"{medal} **{user_stats['username']}**\n"
        leaderboard_text += f"     Points: {user_stats['total_points']} | Accuracy: {accuracy:.1f}% | Streak: {user_stats['best_streak']}\n\n"
    
    embed.add_field(
        name="🎯 Rankings",
        value=leaderboard_text,
        inline=False
    )
    
    embed.set_footer(text=f"Total players: {len(leaderboard_data)} | Use /stats to see your detailed stats")
    
    await ctx.send(embed=embed)

@commands.hybrid_command(name="clear", aliases=["trcl"], description="Clear your stuck trivia session (admin only)")
async def clear_trivia_session(ctx, user: discord.Member = None):
    """Clear a stuck trivia session"""
    # Allow user to clear their own session, or admins to clear any session
    if user and not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Only administrators can clear other users' sessions!", ephemeral=True)
        return
    
    target_user = user or ctx.author
    
    if target_user.id in active_sessions:
        session = active_sessions[target_user.id]
        trivia_logger.info(f"Manually clearing stuck session {session.session_id} for user {target_user.id}")
        
        # Clean up the session
        session.active = False
        session.cleanup_cache()
        del active_sessions[target_user.id]
        
        await ctx.send(f"✅ Cleared stuck trivia session for {target_user.mention}!")
    else:
        await ctx.send(f"❌ {target_user.mention} doesn't have an active trivia session.")

def setup(bot):
    """Setup function for the cog"""
    bot.add_command(trivia)
    bot.add_command(trivia_stats)
    bot.add_command(trivia_leaderboard)
    bot.add_command(clear_trivia_session)