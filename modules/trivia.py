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

# Leaderboard data file path
LEADERBOARD_FILE = os.path.join("data", "trivia_leaderboard.json")

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

def update_user_stats(user_id: int, username: str, is_correct: bool, difficulty: str) -> dict:
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
            "best_streak": 0,
            "current_streak": 0,
            "easy_correct": 0,
            "medium_correct": 0,
            "hard_correct": 0,
            "first_played": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    user_stats = leaderboard_data[user_id_str]
    user_stats["username"] = username  # Update username in case it changed
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
    
    save_leaderboard(leaderboard_data)
    return user_stats

def decode_text(text: str) -> str:
    """Decode HTML entities"""
    return html.unescape(text)

class TriviaSession:
    """Class to manage ongoing trivia sessions"""
    def __init__(self, user_id: int, category: int, difficulty: str, session_token: str = None):
        self.user_id = user_id
        self.category = category
        self.difficulty = difficulty
        self.session_token = session_token
        self.questions_answered = 0
        self.correct_answers = 0
        self.current_streak = 0
        self.session_points = 0
        self.active = True

async def fetch_trivia_question(category_id: int, difficulty: str, session_token: str = None) -> Optional[Dict]:
    """Fetch a trivia question from the API with enhanced error handling"""
    url = "https://opentdb.com/api.php"
    params = {
        "amount": 1,
        "category": category_id,
        "difficulty": difficulty,
        "type": "multiple"  # Can be multiple or boolean
    }
    
    if session_token:
        params["token"] = session_token
    
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url, params=params) as response:
                print(f"API Request URL: {response.url}")
                print(f"API Response Status: {response.status}")
                
                if response.status != 200:
                    print(f"API returned status {response.status}")
                    return None
                
                data = await response.json()
                print(f"API Response Data: {data}")
                
                # Check response code
                if data.get("response_code") == 0 and data.get("results"):
                    return data["results"][0]
                elif data.get("response_code") == 4:  # Token exhausted
                    print("Session token exhausted, trying without token")
                    return await fetch_trivia_question(category_id, difficulty, None)
                else:
                    print(f"API returned error code: {data.get('response_code')}")
                    return None
    
    except Exception as e:
        print(f"Error fetching trivia question: {e}")
        return None

async def get_session_token() -> Optional[str]:
    """Get a session token from the trivia API"""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get("https://opentdb.com/api_token.php?command=request") as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("response_code") == 0:
                        return data.get("token")
    except Exception as e:
        print(f"Error getting session token: {e}")
    return None

async def next_question_callback(interaction: discord.Interaction, session: TriviaSession):
    """Callback to get the next trivia question"""
    try:
        # Fetch the next question
        question_data = await fetch_trivia_question(
            session.category, 
            session.difficulty, 
            session.session_token
        )
        
        if not question_data:
            # Try without session token as fallback
            question_data = await fetch_trivia_question(
                session.category, 
                session.difficulty, 
                None
            )
        
        if not question_data:
            await interaction.response.send_message(
                "❌ Failed to fetch the next trivia question. The session has been ended.",
                ephemeral=True
            )
            session.active = False
            if session.user_id in active_sessions:
                del active_sessions[session.user_id]
            return
        
        # Create new question view
        question_view = TriviaQuestionView(question_data, session, next_question_callback)
        embed = question_view.create_question_embed()
        
        await interaction.response.edit_message(embed=embed, view=question_view)
        
    except Exception as e:
        print(f"Error in next_question_callback: {e}")
        await interaction.response.send_message(
            "❌ An error occurred while fetching the next question.",
            ephemeral=True
        )

class DifficultySelect(discord.ui.View):
    """View for selecting trivia difficulty"""
    def __init__(self, category_id: int, user_id: int):
        super().__init__(timeout=60.0)
        self.category_id = category_id
        self.user_id = user_id
    
    @discord.ui.button(label='Easy', style=discord.ButtonStyle.green)
    async def easy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This trivia session is not for you!", ephemeral=True)
            return
        await self.start_trivia_session(interaction, 'easy')
    
    @discord.ui.button(label='Medium', style=discord.ButtonStyle.primary)
    async def medium_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This trivia session is not for you!", ephemeral=True)
            return
        await self.start_trivia_session(interaction, 'medium')

    @discord.ui.button(label='Hard', style=discord.ButtonStyle.danger)
    async def hard_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This trivia session is not for you!", ephemeral=True)
            return
        await self.start_trivia_session(interaction, 'hard')
    
    async def start_trivia_session(self, interaction: discord.Interaction, difficulty: str):
        """Start a new trivia session"""
        # Check if user already has an active session
        if self.user_id in active_sessions:
            await interaction.response.send_message("❌ You already have an active trivia session! Please finish it first.", ephemeral=True)
            return
        
        # Get session token
        session_token = await get_session_token()
        
        # Create new session
        session = TriviaSession(
            user_id=self.user_id,
            category=self.category_id,
            difficulty=difficulty,
            session_token=session_token
        )
        
        # Store active session
        active_sessions[self.user_id] = session
        
        # Fetch first question
        question_data = await fetch_trivia_question(self.category_id, difficulty, session_token)
        
        if not question_data:
            # Try without session token as fallback
            question_data = await fetch_trivia_question(self.category_id, difficulty, None)
        
        if not question_data:
            await interaction.response.send_message(
                "❌ Failed to fetch trivia question. Please try again later.",
                ephemeral=True
            )
            # Remove the session since it failed
            if self.user_id in active_sessions:
                del active_sessions[self.user_id]
            return
        
        # Create question view
        question_view = TriviaQuestionView(question_data, session, next_question_callback)
        embed = question_view.create_question_embed()
        
        await interaction.response.edit_message(embed=embed, view=question_view)

class TriviaQuestionView(discord.ui.View):
    """View for answering trivia questions"""
    def __init__(self, question_data: Dict, session: TriviaSession, next_question_callback):
        super().__init__(timeout=45.0)
        self.question_data = question_data
        self.session = session
        self.next_question_callback = next_question_callback
        self.answered = False
        
        # Decode all text
        self.question = decode_text(question_data["question"])
        self.correct_answer = decode_text(question_data["correct_answer"])
        self.category = decode_text(question_data["category"])
        
        # Handle answers based on question type
        if question_data["type"] == "boolean":
            self.setup_boolean_buttons()
        else:
            self.setup_multiple_choice_buttons()
        
        # Add stop button
        stop_button = discord.ui.Button(label='Stop Trivia', style=discord.ButtonStyle.secondary, emoji='🛑')
        stop_button.callback = self.stop_trivia
        self.add_item(stop_button)
    
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
            points = {"easy": 1, "medium": 2, "hard": 3}
            self.session.session_points += points[self.session.difficulty]
        else:
            self.session.current_streak = 0
        
        # Update global leaderboard
        user_stats = update_user_stats(
            self.session.user_id, 
            interaction.user.display_name, 
            is_correct, 
            self.session.difficulty
        )
        
        # Create result embed
        embed = self.create_result_embed(answer, is_correct, user_stats)
        
        # Create next question view
        next_view = NextQuestionView(self.session, self.next_question_callback, interaction)
        
        await interaction.response.edit_message(embed=embed, view=next_view)
    
    async def stop_trivia(self, interaction: discord.Interaction):
        """Handle stop trivia button"""
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message("This trivia session is not for you!", ephemeral=True)
            return
        
        self.session.active = False
        if self.session.user_id in active_sessions:
            del active_sessions[self.session.user_id]
        
        # Create final summary embed
        embed = self.create_summary_embed(interaction.user.display_name)
        
        # Disable all buttons
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
    
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
            title=f"{difficulty_emojis[self.session.difficulty]} Trivia Question #{self.session.questions_answered + 1}",
            description=f"**{self.question}**",
            color=difficulty_colors[self.session.difficulty]
        )
        
        embed.add_field(
            name="📚 Category", 
            value=self.category, 
            inline=True
        )
        embed.add_field(
            name="⚡ Difficulty", 
            value=self.session.difficulty.title(), 
            inline=True
        )
        embed.add_field(
            name="🔥 Current Streak", 
            value=str(self.session.current_streak), 
            inline=True
        )
        
        embed.add_field(
            name="<:performance:1417473938681888819> Session Stats",
            value=f"Correct: {self.session.correct_answers}/{self.session.questions_answered} | Points: {self.session.session_points}",
            inline=False
        )
        
        embed.set_footer(text="You have 45 seconds to answer! Click 🛑 to stop trivia.")
        return embed
    
    def create_result_embed(self, user_answer: str, is_correct: bool, user_stats: dict) -> discord.Embed:
        """Create embed showing the result"""
        if is_correct:
            embed = discord.Embed(
                title="<a:verify:1399579399107379271> Correct!",
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
                name="<a:verify:1399579399107379271> Correct Answer",
                value=self.correct_answer,
                inline=True
            )
        
        embed.add_field(
            name="<:performance:1417473938681888819> Session Stats",
            value=f"Questions: {self.session.questions_answered} | Correct: {self.session.correct_answers} | Points: {self.session.session_points} | Streak: {self.session.current_streak}",
            inline=False
        )
        
        embed.add_field(
            name="<:trophy:1417473065134198815> Overall Stats",
            value=f"Total Points: {user_stats['total_points']} | Accuracy: {(user_stats['correct_answers']/user_stats['questions_answered']*100):.1f}% | Best Streak: {user_stats['best_streak']}",
            inline=False
        )
        
        return embed
    
    def create_summary_embed(self, username: str) -> discord.Embed:
        """Create final session summary embed"""
        accuracy = (self.session.correct_answers / max(self.session.questions_answered, 1)) * 100
        
        embed = discord.Embed(
            title="<:CH_BossThumbsUp:1417479389381398540> Trivia Session Complete!",
            description=f"Great job, {username}! Here's your session summary:",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="<:performance:1417473938681888819> Session Results",
            value=f"Questions Answered: {self.session.questions_answered}\nCorrect Answers: {self.session.correct_answers}\nAccuracy: {accuracy:.1f}%\nPoints Earned: {self.session.session_points}",
            inline=True
        )
        
        embed.add_field(
            name="<:CH_BossThumbsUp:1417479389381398540> Category & Difficulty",
            value=f"Category: {TRIVIA_CATEGORIES[self.session.category]['name']}\nDifficulty: {self.session.difficulty.title()}",
            inline=True
        )
        
        embed.set_footer(text="Thanks for playing! Use `/leaderboard` to see rankings.")
        return embed
    
    async def on_timeout(self):
        """Handle timeout"""
        if not self.answered and self.session.active:
            self.session.questions_answered += 1
            self.session.current_streak = 0
            
            # Update stats for timeout (counts as wrong answer)
            update_user_stats(
                self.session.user_id, 
                "Unknown User", 
                False, 
                self.session.difficulty
            )
            
            for item in self.children:
                item.disabled = True
            
            embed = discord.Embed(
                title="<:alarm:1417480889650249728> Time's Up!",
                description=f"**{self.question}**",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="<a:verify:1399579399107379271> Correct Answer",
                value=self.correct_answer,
                inline=False
            )
            
            # Create next question view
            next_view = NextQuestionView(self.session, self.next_question_callback, None)
            
            try:
                # This will fail if the message was deleted, but that's ok
                await self.message.edit(embed=embed, view=next_view)
            except:
                pass

class NextQuestionView(discord.ui.View):
    """View for continuing to next question or stopping"""
    def __init__(self, session: TriviaSession, next_question_callback, interaction):
        super().__init__(timeout=30.0)
        self.session = session
        self.next_question_callback = next_question_callback
        self.interaction = interaction
    
    @discord.ui.button(label='Next Question', style=discord.ButtonStyle.primary, emoji='➡️')
    async def next_question(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message("This trivia session is not for you!", ephemeral=True)
            return
        
        if not self.session.active:
            await interaction.response.send_message("This trivia session has ended!", ephemeral=True)
            return
        
        await self.next_question_callback(interaction, self.session)
    
    @discord.ui.button(label='Stop Trivia', style=discord.ButtonStyle.secondary, emoji='🛑')
    async def stop_trivia(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message("This trivia session is not for you!", ephemeral=True)
            return
        
        self.session.active = False
        if self.session.user_id in active_sessions:
            del active_sessions[self.session.user_id]
        
        # Create final summary embed
        accuracy = (self.session.correct_answers / max(self.session.questions_answered, 1)) * 100
        
        embed = discord.Embed(
            title="<a:verify:1399579399107379271> Trivia Session Complete!",
            description=f"Thanks for playing! Here's your session summary:",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="<:performance:1417473938681888819> Final Results",
            value=f"Questions: {self.session.questions_answered}\nCorrect: {self.session.correct_answers}\nAccuracy: {accuracy:.1f}%\nPoints: {self.session.session_points}",
            inline=False
        )
        
        # Disable all buttons
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def on_timeout(self):
        # Auto-stop session after 30 seconds of inactivity
        self.session.active = False
        if self.session.user_id in active_sessions:
            del active_sessions[self.session.user_id]
        
        for item in self.children:
            item.disabled = True

@commands.hybrid_command(
    name="trivia", 
    aliases=["tr"],
    description="Start a trivia game! Choose from various categories and difficulties."
)
async def trivia(ctx, category: str = None):
    """
    Start a trivia game with the specified category.
    
    Available categories:
    general, books, film, music, tv, games, science, computers, math, 
    mythology, sports, geography, history, politics, art, celebrities, 
    animals, vehicles, anime, cartoons
    """
    
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
            name="<:classification:1417482371170566195> Available Categories",
            value=categories_text,
            inline=False
        )
        
        embed.add_field(
            name="<:bolt:1415190820658745415> Usage",
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
            name="<:classification:1417482371170566195> Available Categories",
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
        title="<:performance:1417473938681888819> Select Difficulty",
        description=f"**Category:** {category_name}\n\nChoose your difficulty level:",
        color=discord.Color.purple()
    )
    
    embed.add_field(
        name="🟢 Easy",
        value="Perfect for beginners! (1 point per question)",
        inline=True
    )
    embed.add_field(
        name="🟡 Medium", 
        value="A good challenge! (2 points per question)",
        inline=True
    )
    embed.add_field(
        name="🔴 Hard",
        value="For trivia masters! (3 points per question)",
        inline=True
    )
    
    embed.set_footer(text="Click a button to start your trivia question!")
    
    view = DifficultySelect(category_id, ctx.author.id)
    await ctx.send(embed=embed, view=view)

@commands.hybrid_command(name="triviastats", aliases=["stats"], description="View your trivia statistics")
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
    accuracy = (stats['correct_answers'] / max(stats['questions_answered'], 1)) * 100
    
    # Calculate average points per question
    avg_points = stats['total_points'] / max(stats['questions_answered'], 1)
    
    embed = discord.Embed(
        title=f"<:trophy:1417473065134198815> Trivia Stats for {stats['username']}",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="<:performance:1417473938681888819> Overall Performance",
        value=f"Questions Answered: {stats['questions_answered']}\nCorrect Answers: {stats['correct_answers']}\nAccuracy: {accuracy:.1f}%\nTotal Points: {stats['total_points']}",
        inline=True
    )
    
    embed.add_field(
        name="<:trophy:1417473065134198815> Records",
        value=f"Best Streak: {stats['best_streak']}\nAvg Points/Question: {avg_points:.1f}\nEasy Correct: {stats['easy_correct']}\nMedium Correct: {stats['medium_correct']}\nHard Correct: {stats['hard_correct']}",
        inline=True
    )
    
    # Rank calculation
    sorted_users = sorted(leaderboard_data.values(), key=lambda x: x['total_points'], reverse=True)
    rank = next((i+1 for i, user in enumerate(sorted_users) if user['user_id'] == user_id), "N/A")
    
    embed.add_field(
        name="<:trophy:1417473065134198815> Ranking",
        value=f"Global Rank: #{rank} out of {len(leaderboard_data)} players",
        inline=False
    )
    
    embed.set_thumbnail(url=target_user.display_avatar.url)
    embed.set_footer(text=f"First played: {stats['first_played']}")
    
    await ctx.send(embed=embed)

@commands.hybrid_command(name="leaderboard", aliases=["lead", "trivia_top"], description="View the trivia leaderboard")
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
        title="<:trophy:1417473065134198815> Trivia Leaderboard",
        description=f"Top trivia players (Page {page}/{total_pages})",
        color=discord.Color.gold()
    )
    
    leaderboard_text = ""
    for i, user_stats in enumerate(page_users, start=start_idx + 1):
        accuracy = (user_stats['correct_answers'] / max(user_stats['questions_answered'], 1)) * 100
        
        # Medal emojis for top 3
        if i == 1:
            medal = "<:medal1:1417483730619990117>"
        elif i == 2:
            medal = "<:medal2:1417483748089397248>"
        elif i == 3:
            medal = "<:medal3:1417483764875001886>"
        else:
            medal = f"**{i}.**"
        
        leaderboard_text += f"{medal} **{user_stats['username']}**\n"
        leaderboard_text += f"     Points: {user_stats['total_points']} | Accuracy: {accuracy:.1f}% | Streak: {user_stats['best_streak']}\n\n"
    
    embed.add_field(
        name="<:trophy:1417473065134198815> Rankings",
        value=leaderboard_text,
        inline=False
    )
    
    embed.set_footer(text=f"Total players: {len(leaderboard_data)} | Use /stats to see your detailed stats")
    
    await ctx.send(embed=embed)

def setup(bot):
    """Setup function for the cog"""
    bot.add_command(trivia)
    bot.add_command(trivia_stats)
    bot.add_command(trivia_leaderboard)