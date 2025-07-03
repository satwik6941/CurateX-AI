import os
import logging
import asyncio
from datetime import datetime, timedelta
import schedule
import time
import threading
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
import dotenv as env

# Import our existing modules
import search
# Import the LLM module
import llm
# Import RAG module for handling post-news questions
import rag

import curatex_bot

# Load environment variables
env.load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
QUERY, NEWS_COUNT, DELIVERY_TIME, CONFIRM = range(4)

# User data storage
user_sessions = {}

# Track users who have received news and can ask questions
users_with_news_context = set()

class NewsCuratorBot:
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")
        
        # Verify that required modules are available
        self._verify_modules()
    
    def _verify_modules(self):
        """Verify that required modules and their functions are available"""
        try:
            # Check if search module has required functions
            if not hasattr(search, 'main'):
                logger.warning("search.py should have a main() function")
            if not hasattr(search, 'set_user_query'):
                logger.warning("search.py should have a set_user_query() function")
            
            # Check if llm module has required functions with detailed inspection
            logger.info(f"LLM module attributes: {[attr for attr in dir(llm) if not attr.startswith('_')]}")
            
            if not hasattr(llm, 'main'):
                logger.error("❌ llm.py does not have a main() function")
                # Try to find alternative function names
                possible_functions = ['main', 'process', 'curate', 'run']
                found_functions = [func for func in possible_functions if hasattr(llm, func)]
                if found_functions:
                    logger.info(f"Found alternative functions: {found_functions}")
                else:
                    logger.error("No suitable entry point found in llm.py")
            else:
                logger.info("✅ llm.py main() function found")
            
            # Check if global variables exist
            if hasattr(llm, 'user_query'):
                logger.info("✅ llm.user_query variable found")
            else:
                logger.warning("⚠️ llm.user_query variable not found")
                
            if hasattr(llm, 'news_number'):
                logger.info("✅ llm.news_number variable found")
            else:
                logger.warning("⚠️ llm.news_number variable not found")
            
            # Check RAG module
            if hasattr(rag, 'setup_news_rag'):
                logger.info("✅ rag.py setup_news_rag() function found")
            else:
                logger.warning("⚠️ rag.py setup_news_rag() function not found")
                
            if hasattr(rag, 'answer_news_question'):
                logger.info("✅ rag.py answer_news_question() function found")
            else:
                logger.warning("⚠️ rag.py answer_news_question() function not found")
                
            logger.info("✅ Module verification completed")
            
        except Exception as e:
            logger.error(f"❌ Module verification error: {e}")
            print(f"❌ Module verification failed: {e}")
            print("💡 Make sure search.py, llm.py, and rag.py are in the same directory")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        welcome_message = f"""
🤖 **Welcome to CurateX AI News Bot, {user.first_name}!**

I'm your personal news curator powered by AI. Here's how it works:

**� All inputs collected via Telegram:**
• Use `/input` to start - I'll collect all your preferences
• No external input needed - everything happens in this chat!

**🔄 Complete Processing Pipeline:**
1. 🎯 Collect your search query and preferences via `/input`
2. � Pass query to `search.py` for article discovery  
3. 🎯 Pass parameters to `llm.py` for AI curation
4. 📤 Deliver results back to you in Telegram
5. 💬 **Ask me questions about the news - I'll answer using AI!**

**📋 Available Commands:**
• `/input` - Start news curation (collects all inputs)
• `/help` - Show detailed usage guide
• `/cancel` - Cancel current operation

**💡 After receiving curated news:**
• Just send me any question about the articles
• I'll use AI-powered search to find answers from your curated content
• Perfect for clarifications, deeper insights, or follow-up questions!

**🚀 Ready to start?** Just type `/input` or say "hi"!
        """
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
🔧 **CurateX AI - Complete Input Collection via Telegram**

**📱 How it works:**
All user inputs are collected through this Telegram bot using `/input`

**🔄 Processing Flow:**
1. **Input Collection** (via `/input`):
   • Your search query/topic
   • Number of articles to curate (1-50)  
   • Delivery preferences (now/scheduled)

2. **Automated Processing:**
   • 🔍 `search.py` receives your query
   • 🎯 `llm.py` receives query + article count
   • 📝 AI processes and curates content
   • 📤 Results delivered via Telegram

3. **Interactive Q&A:**
   • 💬 After receiving news, ask me any questions!
   • 🧠 I'll use AI-powered RAG to answer from your curated articles
   • 🔄 Maintains conversation context for follow-up questions

**🎯 Key Features:**
• **No external input needed** - everything via Telegram
• **AI-powered curation** with multiple sources
• **Detailed summaries** and analysis
• **Interactive Q&A** about your curated news
• **Scheduled delivery** options
• **Quality filtering** and ranking

**📝 Usage Tips:**
• Be specific with queries for better results
• More articles = better curation but longer processing
• Ask follow-up questions about the news after delivery
• Use `/cancel` anytime to restart
• All your preferences are saved during the session

**🚀 Ready?** Type `/input` to start collecting your preferences!
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def greeting_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle greetings and general messages, including questions about news"""
        message_text = update.message.text.lower()
        user_id = update.effective_user.id
        greetings = ['hi', 'hello', 'hey', 'start', 'begin']
        
        # Check if the message is a button click (contains command)
        if any(cmd in update.message.text for cmd in ['/input', '/help', '/start']):
            # Don't handle button clicks here - let the command handlers take care of them
            return
        
        # If user has news context and this isn't a greeting, treat it as a question
        if user_id in users_with_news_context and not any(greeting in message_text for greeting in greetings):
            await self.handle_news_question(update, context)
            return
        
        if any(greeting in message_text for greeting in greetings):
            keyboard = [
                ['📰 /input - Start News Curation'],
                ['❓ /help - How to Use'],
                ['ℹ️ /start - Welcome Message']
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            
            response_text = "👋 Hello! What would you like to do today?"
            
            # Add news context info if user has it
            if user_id in users_with_news_context:
                response_text += "\n\n💬 **You can also ask me questions about your curated news!**"
            
            await update.message.reply_text(
                response_text,
                reply_markup=reply_markup
            )
        else:
            # If user has news context, suggest they can ask questions
            if user_id in users_with_news_context:
                await update.message.reply_text(
                    "💬 I can help answer questions about your curated news!\n\n"
                    "Just ask me anything about the articles I shared with you, or use:\n"
                    "• /input - Get new curated news\n"
                    "• /help - Learn how to use the bot"
                )
            else:
                await update.message.reply_text(
                    "I didn't understand that. Try saying 'hi' or use /help for available commands."
                )
    
    async def start_input_flow(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start the input collection conversation"""
        user_id = update.effective_user.id
        
        # Clear any existing session data to start fresh
        if user_id in user_sessions:
            del user_sessions[user_id]
        
        user_sessions[user_id] = {}
        
        logger.info(f"User {user_id} started input flow")
        
        await update.message.reply_text(
            "🎯 **CurateX AI News Curation Setup**\n\n"
            "I'll collect all your preferences and then process everything automatically!\n\n"
            "**Step 1 of 3: Search Query**\n"
            "What topic would you like me to search for?\n\n"
            "Examples:\n"
            "• 'artificial intelligence trends'\n"
            "• 'climate change solutions'\n"
            "• 'latest tech innovations'\n"
            "• 'cryptocurrency market news'",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='Markdown'
        )
        return QUERY
    
    async def collect_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Collect the search query"""
        user_id = update.effective_user.id
        query = update.message.text.strip()
        
        logger.info(f"User {user_id} provided query: {query}")
        
        if len(query) < 3:
            await update.message.reply_text(
                "⚠️ Please provide a more specific query (at least 3 characters)."
            )
            return QUERY
        
        user_sessions[user_id]['query'] = query
        
        # Show number selection keyboard
        keyboard = [
            ['5', '10', '15'],
            ['20', '25', '30'],
            ['Custom Amount']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            f"✅ **Query Saved:** '{query}'\n\n"
            "**Step 2 of 3: Article Count**\n"
            "📊 How many articles would you like me to curate? (1-50)\n\n"
            "💡 More articles = better curation but longer processing time",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return NEWS_COUNT
    
    async def collect_news_count(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Collect the number of articles"""
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        if text == "Custom Amount":
            await update.message.reply_text(
                "Enter your desired number of articles (1-50):",
                reply_markup=ReplyKeyboardRemove()
            )
            return NEWS_COUNT
        
        try:
            count = int(text)
            if count < 1 or count > 50:
                await update.message.reply_text(
                    "⚠️ Please enter a number between 1 and 50."
                )
                return NEWS_COUNT
        except ValueError:
            await update.message.reply_text(
                "⚠️ Please enter a valid number."
            )
            return NEWS_COUNT
        
        user_sessions[user_id]['news_count'] = count
        
        # Show delivery options
        keyboard = [
            ['📤 Send Now'],
            ['⏰ Schedule for Later'],
            ['📅 Daily at Specific Time']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            f"✅ **Article Count:** {count} articles\n\n"
            "**Step 3 of 3: Delivery Preference**\n"
            "⏰ When would you like to receive the curated news?\n\n"
            "📤 **Send Now** - Process and deliver immediately\n"
            "⏰ **Schedule for Later** - Set a specific time today\n"
            "📅 **Daily at Specific Time** - Set up daily delivery",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return DELIVERY_TIME
    
    async def collect_delivery_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Collect delivery preferences"""
        user_id = update.effective_user.id
        choice = update.message.text.strip()
        
        user_sessions[user_id]['delivery_option'] = choice
        
        if choice == "📤 Send Now":
            user_sessions[user_id]['delivery_time'] = "now"
        elif choice == "⏰ Schedule for Later":
            await update.message.reply_text(
                "⏰ When would you like to receive it? (Format: HH:MM, e.g., 14:30)",
                reply_markup=ReplyKeyboardRemove()
            )
            return DELIVERY_TIME
        elif choice == "📅 Daily at Specific Time":
            await update.message.reply_text(
                "📅 What time daily? (Format: HH:MM, e.g., 09:00)",
                reply_markup=ReplyKeyboardRemove()
            )
            return DELIVERY_TIME
        else:
            # Handle time input for scheduled delivery
            try:
                time_obj = datetime.strptime(choice, "%H:%M").time()
                user_sessions[user_id]['delivery_time'] = choice
            except ValueError:
                await update.message.reply_text(
                    "⚠️ Invalid time format. Please use HH:MM (e.g., 14:30)"
                )
                return DELIVERY_TIME
        
        return await self.show_confirmation(update, context)
    
    async def show_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show confirmation of all inputs"""
        user_id = update.effective_user.id
        session = user_sessions[user_id]
        
        confirmation_text = f"""
📋 **Input Collection Complete!**

🎯 **Search Query:** {session['query']}
📊 **Articles to Curate:** {session['news_count']}
⏰ **Delivery Method:** {session.get('delivery_option', 'Send Now')}
"""
        
        if session.get('delivery_time') and session['delivery_time'] != 'now':
            confirmation_text += f"🕐 **Scheduled Time:** {session['delivery_time']}\n"
        
        confirmation_text += f"""

**🔄 Processing Pipeline:**
1. 🔍 **search.py** will search for articles using your query
2. 🎯 **llm.py** will curate the top {session['news_count']} articles  
3. 📝 **Format** and prepare the results
4. 📤 **Deliver** via Telegram

✅ **Ready to start?** This will take a few minutes to complete.
"""
        
        keyboard = [
            ['✅ Yes, Start Processing'],
            ['❌ Cancel', '✏️ Edit Settings']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            confirmation_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return CONFIRM
    
    async def handle_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the final confirmation"""
        user_id = update.effective_user.id
        choice = update.message.text.strip()
        
        if choice == "✅ Yes, Start Processing":
            await update.message.reply_text(
                "🚀 **Starting CurateX AI Processing...**\n\n"
                "📊 All inputs collected from Telegram bot\n"
                "🔄 Now passing to processing modules\n"
                "⏱️ This will take a few minutes...",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode='Markdown'
            )
            
            # Start the curation process with all collected inputs
            await self.process_news_curation(update, context, user_sessions[user_id])
            
        elif choice == "❌ Cancel":
            await update.message.reply_text(
                "❌ Processing cancelled. Use /input to start again.",
                reply_markup=ReplyKeyboardRemove()
            )
        elif choice == "✏️ Edit Settings":
            await update.message.reply_text(
                "✏️ Let's restart input collection. Use /input to begin again.",
                reply_markup=ReplyKeyboardRemove()
            )
        
        # Clean up session
        if user_id in user_sessions:
            del user_sessions[user_id]
        
        return ConversationHandler.END
    
    async def process_news_curation(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session_data):
        """Process the complete news curation workflow with all inputs from Telegram"""
        try:
            # Extract all user inputs collected from Telegram bot
            query = session_data['query']
            news_count = session_data['news_count']
            delivery_time = session_data.get('delivery_time', 'now')
            
            await update.message.reply_text(
                f"📋 **Processing with User Inputs:**\n"
                f"🎯 Query: '{query}'\n"
                f"📊 Articles: {news_count}\n"
                f"⏰ Delivery: {session_data.get('delivery_option', 'Now')}\n\n"
                f"🔄 Starting pipeline...",
                parse_mode='Markdown'
            )
            
            # Step 1: Pass query to search.py
            await update.message.reply_text("🔍 **Step 1/4:** Passing query to search.py module...")
            search_results = await self.run_search(query)
            
            if not search_results:
                await update.message.reply_text(
                    "❌ Search module failed. No articles found for your query.\n"
                    "Please try a different search term with /input"
                )
                return
            
            # Verify that news_results.txt was created by search.py
            if not os.path.exists('news_results.txt'):
                await update.message.reply_text(
                    "❌ Search module failed to create results file.\n"
                    "Please try again with /input"
                )
                return
            
            # Step 2: Pass query and count to llm.py
            await update.message.reply_text(f"🎯 **Step 2/4:** Passing inputs to llm.py for curation of {news_count} articles...")
            curated_files = await self.run_curation(query, news_count)
            
            if not curated_files:
                await update.message.reply_text(
                    "❌ Curation module failed. Please try again with /input"
                )
                return
            
            # Step 3: Verify files were created
            await update.message.reply_text("📝 **Step 3/4:** Verifying generated files...")
            
            # Check if files exist
            missing_files = [f for f in curated_files if not os.path.exists(f)]
            if missing_files:
                await update.message.reply_text(
                    f"⚠️ Warning: Some files were not created: {missing_files}"
                )
            
            # Step 4: Process delivery based on user input
            await update.message.reply_text("📤 **Step 4/4:** Processing delivery based on your preferences...")
            
            if delivery_time == 'now':
                await self.send_results(update, curated_files)
            else:
                await self.schedule_delivery(update, context, curated_files, delivery_time)
            
        except Exception as e:
            logger.error(f"Error in curation pipeline: {e}")
            await update.message.reply_text(
                f"❌ An error occurred during processing: {str(e)}\n\n"
                "🔄 All your inputs from /input have been collected successfully.\n"
                "Please try running /input again."
            )
    
    async def run_search(self, query):
        """Run the search module"""
        try:
            # Run search function in a thread since it's not async
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(None, self._run_search_sync, query)
            return results
        except Exception as e:
            logger.error(f"Search error: {e}")
            return None
    
    def _run_search_sync(self, query):
        """Synchronous wrapper for search function - passes Telegram input to search.py"""
        try:
            logger.info(f"📤 Passing query to search.py: '{query}'")
            
            # Set the user_query in search module (input from Telegram bot)
            search.set_user_query(query)
            
            # Call the search module's main function
            result = search.main()
            
            logger.info(f"✅ Search.py completed successfully")
            return result
        except Exception as e:
            logger.error(f"❌ Search.py execution error: {e}")
            return False
    
    async def run_curation(self, query, count):
        """Run the curation module"""
        try:
            # Run curation in a thread since it's not async
            loop = asyncio.get_event_loop()
            files = await loop.run_in_executor(None, self._run_curation_sync, query, count)
            return files
        except Exception as e:
            logger.error(f"Curation error: {e}")
            return None
    
    def _run_curation_sync(self, query, count):
        """Synchronous wrapper for curation function - passes Telegram inputs to llm.py"""
        try:
            logger.info(f"📤 Passing inputs to llm.py: query='{query}', count={count}")
            
            # Debug: Check if llm module is properly imported
            logger.info(f"LLM module type: {type(llm)}")
            logger.info(f"LLM module file: {getattr(llm, '__file__', 'Unknown')}")
            
            # Set the parameters in llm module (inputs from Telegram bot)
            if hasattr(llm, 'user_query'):
                llm.user_query = query
                logger.info(f"✅ Set llm.user_query = '{query}'")
            else:
                logger.error("❌ llm.user_query attribute not found")
                
            if hasattr(llm, 'news_number'):
                llm.news_number = count
                logger.info(f"✅ Set llm.news_number = {count}")
            else:
                logger.error("❌ llm.news_number attribute not found")
            
            # Check if main function exists before calling
            if not hasattr(llm, 'main'):
                logger.error("❌ llm.main function not found")
                logger.info(f"Available functions: {[attr for attr in dir(llm) if callable(getattr(llm, attr)) and not attr.startswith('_')]}")
                raise AttributeError("llm module has no attribute 'main'")
            
            # Call the llm module's main function
            logger.info("🔄 Calling llm.main()...")
            result = llm.main()
            logger.info(f"✅ llm.main() returned: {result}")
            
            # Return the generated file paths
            output_filename = f"curated_news_{count}_articles.txt"
            message_filename = f"formatted_message_{count}_articles.txt"
            
            files = []
            if os.path.exists(output_filename):
                files.append(output_filename)
                logger.info(f"✅ Created: {output_filename}")
            if os.path.exists(message_filename):
                files.append(message_filename)
                logger.info(f"✅ Created: {message_filename}")
            
            if not files:
                logger.warning("⚠️ No output files were created by llm.py")
            
            logger.info(f"✅ LLM.py completed successfully, generated {len(files)} files")
            return files
            
        except AttributeError as e:
            logger.error(f"❌ LLM.py attribute error: {e}")
            logger.info("💡 This usually means the llm.py file doesn't have the expected functions or variables")
            return None
        except Exception as e:
            logger.error(f"❌ LLM.py execution error: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            return None

    async def send_results(self, update, files):
        """Send the curated results to user"""
        try:
            chat_id = update.effective_chat.id
            user_id = update.effective_user.id
            
            await update.message.reply_text(
                "✅ **Curation Complete!**\n\n"
                "📎 Sending your curated news files...",
                parse_mode='Markdown'
            )
            
            # Send files directly using the bot
            if files:
                for file_path in files:
                    if os.path.exists(file_path):
                        # Send as document
                        with open(file_path, 'rb') as file:
                            await update.message.reply_document(
                                document=file,
                                filename=os.path.basename(file_path),
                                caption=f"📰 {os.path.basename(file_path)}"
                            )
                        await asyncio.sleep(1)  # Rate limiting
                
                # Also send the message content as text for easy reading
                message_files = [f for f in files if 'formatted_message' in f]
                if message_files:
                    try:
                        with open(message_files[0], 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Split into chunks if too long (Telegram limit ~4096 chars)
                            chunks = [content[i:i+4000] for i in range(0, len(content), 4000)]
                            for i, chunk in enumerate(chunks):
                                await update.message.reply_text(
                                    f"📰 **News Summary (Part {i+1}/{len(chunks)}):**\n\n{chunk}",
                                    parse_mode='Markdown'
                                )
                                await asyncio.sleep(1)
                    except UnicodeDecodeError:
                        # Try with different encoding if UTF-8 fails
                        with open(message_files[0], 'r', encoding='latin-1') as f:
                            content = f.read()
                            await update.message.reply_text(
                                f"📰 **News Summary:**\n\n{content[:4000]}",
                                parse_mode='Markdown'
                            )
            
            # Setup RAG system with the curated news files for future questions
            await self.setup_rag_for_user(user_id, files)
            
            await update.message.reply_text(
                "🎉 **All done!** Your curated news has been delivered.\n\n"
                "💬 **You can now ask me questions about the news!**\n"
                "Just send me any question and I'll answer using the context of your curated articles.\n\n"
                "Use /input for another curation request.",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Send error: {e}")
            await update.message.reply_text(
                f"❌ Error sending files: {str(e)}"
            )
    
    async def schedule_delivery(self, update, context, files, delivery_time):
        """Schedule delivery for later using curatex_bot functionality"""
        try:
            user_id = update.effective_user.id
            
            # Find the message file (formatted_message_*.txt)
            message_files = [f for f in files if 'formatted_message' in f]
            
            if message_files:
                # Copy the formatted message file to messages_to_user.txt for curatex_bot
                import shutil
                shutil.copy(message_files[0], 'messages_to_user.txt')
                
                # Setup RAG system for this user even with scheduled delivery
                await self.setup_rag_for_user(user_id, files)
                
                # Parse the delivery time
                delivery_hour, delivery_minute = map(int, delivery_time.split(':'))
                
                await update.message.reply_text(
                    f"⏰ **Scheduled Successfully!**\n\n"
                    f"Your curated news will be delivered daily at {delivery_time}\n"
                    f"The CurateX bot will send you the messages automatically.\n\n"
                    f"📝 Messages have been prepared and saved.\n"
                    f"🤖 Background scheduler is now active.\n\n"
                    f"💬 **You can now ask me questions about the curated news!**\n"
                    f"Just send me any question and I'll search through your articles.",
                    parse_mode='Markdown'
                )
                
                # You can integrate with curatex_bot's scheduling functionality here
                # For now, we'll just save the schedule preference
                logger.info(f"News scheduled for delivery at {delivery_time}")
                
            else:
                await update.message.reply_text(
                    "❌ Error: No message file found for scheduling."
                )
                
        except Exception as e:
            logger.error(f"Scheduling error: {e}")
            await update.message.reply_text(
                f"❌ Error scheduling delivery: {str(e)}"
            )
    
    async def cancel_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel the current conversation"""
        user_id = update.effective_user.id
        if user_id in user_sessions:
            del user_sessions[user_id]
        
        # If it's a specific command, handle it appropriately
        if update.message.text.startswith('/start'):
            await self.start_command(update, context)
        elif update.message.text.startswith('/help'):
            await self.help_command(update, context)
        else:
            await update.message.reply_text(
                "❌ Operation cancelled. Use /input to start again.",
                reply_markup=ReplyKeyboardRemove()
            )
        return ConversationHandler.END
    
    async def restart_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Restart the conversation when /input is called during an active conversation"""
        user_id = update.effective_user.id
        
        # Clean up existing session
        if user_id in user_sessions:
            del user_sessions[user_id]
        
        await update.message.reply_text(
            "🔄 **Restarting Input Collection...**\n\n"
            "Previous session cleared. Starting fresh!",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='Markdown'
        )
        
        # End current conversation - the entry point will handle the new start
        return ConversationHandler.END
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors that occur during bot operation"""
        logger.error(f"Exception while handling an update: {context.error}")
        
        # Try to send an error message to the user if possible
        if update and hasattr(update, 'effective_chat') and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ Sorry, an error occurred. Please try again with /input or /start."
                )
            except Exception as e:
                logger.error(f"Failed to send error message: {e}")

    def create_application(self):
        """Create and configure the bot application"""
        # Add job queue to handle conversation timeouts
        application = Application.builder().token(self.bot_token).build()
        
        # Conversation handler for input flow
        input_conversation = ConversationHandler(
            entry_points=[CommandHandler('input', self.start_input_flow)],
            states={
                QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_query)],
                NEWS_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_news_count)],
                DELIVERY_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_delivery_time)],
                CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_confirmation)],
            },
            fallbacks=[
                CommandHandler('cancel', self.cancel_conversation),
                CommandHandler('input', self.restart_conversation),  # Restart conversation
                MessageHandler(filters.COMMAND, self.cancel_conversation)  # Handle any other commands
            ],
            allow_reentry=False,  # Prevent re-entry issues
            conversation_timeout=None,  # Disable timeout to avoid JobQueue requirement
            per_chat=True,
            per_user=True,
            per_message=False,
        )
        
        # Add handlers in the correct order (no duplicate input handler)
        application.add_handler(CommandHandler('start', self.start_command))
        application.add_handler(CommandHandler('help', self.help_command))
        application.add_handler(input_conversation)  # This handles /input
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.greeting_handler))
        
        # Add error handler
        application.add_error_handler(self.error_handler)
        
        return application
    
    def run(self):
        """Start the bot"""
        application = self.create_application()
        
        logger.info("🤖 CurateX AI Bot starting...")
        logger.info("📋 Workflow: User Input -> Search -> Curation -> Formatting -> Delivery -> Q&A")
        logger.info("🔗 Integrating: search.py -> llm.py -> curatex_bot.py -> rag.py")
        
        print("🤖 CurateX AI Bot is running...")
        print("📱 Send 'hi' to your bot to get started!")
        print("🔄 Workflow ready: Search -> Curate -> Format -> Deliver -> Q&A")
        print("💬 New: Ask questions about your curated news using AI-powered RAG!")
        
        # Run the bot
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    def cleanup_temp_files(self):
        """Clean up temporary files created during the process"""
        temp_files = ['news_results.txt', 'messages_to_user.txt']
        for file in temp_files:
            try:
                if os.path.exists(file):
                    os.remove(file)
                    logger.info(f"Cleaned up {file}")
            except Exception as e:
                logger.error(f"Error cleaning up {file}: {e}")

    async def setup_rag_for_user(self, user_id, news_files):
        """Setup RAG system with curated news files for answering user questions"""
        try:
            logger.info(f"Setting up RAG system for user {user_id}")
            
            # Copy the curated news files to the data directory for RAG
            import shutil
            data_dir = "data"
            
            # Ensure data directory exists
            os.makedirs(data_dir, exist_ok=True)
            
            # Copy curated news files to data directory
            for file_path in news_files:
                if os.path.exists(file_path):
                    dest_path = os.path.join(data_dir, os.path.basename(file_path))
                    shutil.copy2(file_path, dest_path)
                    logger.info(f"Copied {file_path} to {dest_path}")
            
            # Also copy news_results.txt if it exists
            if os.path.exists('news_results.txt'):
                shutil.copy2('news_results.txt', os.path.join(data_dir, 'news_results.txt'))
                logger.info("Copied news_results.txt to data directory")
            
            # Setup the RAG system with the news files
            loop = asyncio.get_event_loop()
            rag_setup_success = await loop.run_in_executor(None, rag.setup_news_rag, data_dir)
            
            if rag_setup_success:
                # Add user to the set of users who can ask questions
                users_with_news_context.add(user_id)
                logger.info(f"✅ RAG system setup successful for user {user_id}")
            else:
                logger.warning(f"⚠️ RAG system setup failed for user {user_id}")
                
        except Exception as e:
            logger.error(f"Error setting up RAG for user {user_id}: {e}")
    
    async def handle_news_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user questions about the news using RAG system"""
        user_id = update.effective_user.id
        question = update.message.text.strip()
        
        # Check if this user has news context
        if user_id not in users_with_news_context:
            await update.message.reply_text(
                "🤔 I don't have any news context for you yet.\n\n"
                "Please use /input to curate some news first, then I can answer questions about it!",
                parse_mode='Markdown'
            )
            return
        
        try:
            await update.message.reply_text(
                "🤔 **Thinking about your question...**\n\n"
                "Searching through your curated news to find the answer...",
                parse_mode='Markdown'
            )
            
            # Use RAG system to answer the question
            loop = asyncio.get_event_loop()
            answer = await loop.run_in_executor(None, self._answer_question_sync, question)
            
            if answer:
                # Split long answers into chunks
                max_length = 4000
                if len(answer) > max_length:
                    chunks = [answer[i:i+max_length] for i in range(0, len(answer), max_length)]
                    for i, chunk in enumerate(chunks):
                        await update.message.reply_text(
                            f"💬 **Answer (Part {i+1}/{len(chunks)}):**\n\n{chunk}",
                            parse_mode='Markdown'
                        )
                        await asyncio.sleep(1)
                else:
                    await update.message.reply_text(
                        f"💬 **Answer:**\n\n{answer}",
                        parse_mode='Markdown'
                    )
                    
                await update.message.reply_text(
                    "❓ **Have more questions?** Just ask me anything about the news!\n"
                    "Or use /input to get new curated news.",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    "❌ Sorry, I couldn't find an answer to your question in the curated news.\n\n"
                    "Try rephrasing your question or use /input to get fresh news content.",
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Error answering question: {e}")
            await update.message.reply_text(
                f"❌ An error occurred while processing your question: {str(e)}\n\n"
                "Please try asking again or use /input for new news curation.",
                parse_mode='Markdown'
            )
    
    def _answer_question_sync(self, question):
        """Synchronous wrapper for RAG question answering"""
        try:
            # Use the async function from rag module
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                answer = loop.run_until_complete(rag.answer_news_question(question))
                return answer
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Error in sync question answering: {e}")
            return None

def main():
    """Main function"""
    try:
        print("🚀 Initializing CurateX AI News Curation System...")
        print("📋 Workflow: User Query -> Search (search.py) -> Curate (llm.py) -> Format -> Deliver (curatex_bot.py)")
        print("💬 New Feature: RAG-powered Q&A about curated news using rag.py")
        
        bot = NewsCuratorBot()
        bot.run()
        
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
        logger.info("Bot stopped by user interrupt")
        
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        logger.error(f"Configuration error: {e}")
        
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        logger.error(f"Bot startup error: {e}")
        print("💡 Check your configuration and try again")

if __name__ == '__main__':
    main()
