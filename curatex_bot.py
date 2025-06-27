from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
import os
import dotenv as env
import logging
from groq import Groq
import asyncio
from datetime import datetime, time
import pytz
import re

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

env.load_dotenv()

client = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
)

BOT_TOKEN = os.getenv("TELEGRAM_API_KEY")

# Global variables for scheduling
scheduled_messages = []
current_message_index = 0
scheduled_time = None
target_chat_id = None
is_scheduling_active = False
user_states = {}  # Track user interaction states

def load_messages_from_file():
    """Load messages from messages_to_user.txt file"""
    try:
        with open("messages_to_user.txt", "r", encoding="utf-8") as f:
            content = f.read().strip()
        
        # Split messages by double newlines (each message block)
        messages = []
        current_message = []
        
        for line in content.split('\n'):
            line = line.strip()
            if line:
                current_message.append(line)
            else:
                if current_message:
                    # Join the lines of current message
                    full_message = '\n'.join(current_message)
                    messages.append(full_message)
                    current_message = []
        
        # Add the last message if exists
        if current_message:
            full_message = '\n'.join(current_message)
            messages.append(full_message)
        
        logger.info(f"Loaded {len(messages)} messages from file")
        
        # Print all messages in terminal for verification
        print_messages_preview(messages)
        
        return messages
    
    except FileNotFoundError:
        logger.error("messages_to_user.txt file not found")
        return []
    except Exception as e:
        logger.error(f"Error loading messages: {e}")
        return []

def print_messages_preview(messages):
    """Print all loaded messages in terminal for verification"""
    print("\n" + "="*80)
    print("📰 NEWS MESSAGES LOADED - TERMINAL PREVIEW")
    print("="*80)
    
    if not messages:
        print("❌ NO MESSAGES FOUND!")
        return
    
    print(f"📊 Total Messages: {len(messages)}")
    print("-" * 80)
    
    for i, message in enumerate(messages, 1):
        print(f"\n📰 MESSAGE {i}/{len(messages)}:")
        print("-" * 40)
        print(message)
        print("-" * 40)
    
    print("\n" + "="*80)
    print("✅ ALL MESSAGES PREVIEW COMPLETE")
    print("="*80)

def parse_time(time_str):
    """Parse time string in 12-hour format (e.g., '2:30 PM') to time object"""
    try:
        # Remove extra spaces and convert to uppercase
        time_str = time_str.strip().upper()
        
        # Parse 12-hour format
        time_obj = datetime.strptime(time_str, "%I:%M %p").time()
        return time_obj
    except ValueError:
        return None

async def send_scheduled_message(context):
    """Send the next scheduled message"""
    global current_message_index, scheduled_messages, target_chat_id, is_scheduling_active
    
    if not is_scheduling_active or not scheduled_messages:
        return
    
    if current_message_index < len(scheduled_messages):
        message = scheduled_messages[current_message_index]
        
        try:
            await context.bot.send_message(
                chat_id=target_chat_id,
                text=message,
                parse_mode='HTML'
            )
            
            logger.info(f"Sent message {current_message_index + 1}/{len(scheduled_messages)}")
            current_message_index += 1
            
            # Check if all messages are sent
            if current_message_index >= len(scheduled_messages):
                is_scheduling_active = False
                await context.bot.send_message(
                    chat_id=target_chat_id,
                    text="✅ All scheduled messages have been sent!"
                )
                logger.info("All scheduled messages sent")
            
        except Exception as e:
            logger.error(f"Error sending scheduled message: {e}")
    else:
        is_scheduling_active = False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"User {update.effective_user.first_name} started the bot")
    await update.message.reply_text(
        "Hi! I'm your CurateX AI bot.\n\n"
        "Commands:\n"
        "• Chat normally for AI responses\n"
        "• /schedule <time> - Schedule messages (e.g., '/schedule 2:30 PM')\n"
        "• /stop - Stop scheduled messages\n"
        "• /status - Check scheduling status"
    )

async def schedule_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the scheduling process with interactive time selection"""
    global user_states
    
    user_id = update.effective_user.id
    user_states[user_id] = {'step': 'awaiting_time'}
    
    # Create time selection keyboard
    keyboard = [
        [
            InlineKeyboardButton("6:00 AM", callback_data="time_06:00_AM"),
            InlineKeyboardButton("7:00 AM", callback_data="time_07:00_AM"),
            InlineKeyboardButton("8:00 AM", callback_data="time_08:00_AM")
        ],
        [
            InlineKeyboardButton("9:00 AM", callback_data="time_09:00_AM"),
            InlineKeyboardButton("10:00 AM", callback_data="time_10:00_AM"),
            InlineKeyboardButton("11:00 AM", callback_data="time_11:00_AM")
        ],
        [
            InlineKeyboardButton("12:00 PM", callback_data="time_12:00_PM"),
            InlineKeyboardButton("1:00 PM", callback_data="time_01:00_PM"),
            InlineKeyboardButton("2:00 PM", callback_data="time_02:00_PM")
        ],
        [
            InlineKeyboardButton("3:00 PM", callback_data="time_03:00_PM"),
            InlineKeyboardButton("4:00 PM", callback_data="time_04:00_PM"),
            InlineKeyboardButton("5:00 PM", callback_data="time_05:00_PM")
        ],
        [
            InlineKeyboardButton("6:00 PM", callback_data="time_06:00_PM"),
            InlineKeyboardButton("7:00 PM", callback_data="time_07:00_PM"),
            InlineKeyboardButton("8:00 PM", callback_data="time_08:00_PM")
        ],
        [
            InlineKeyboardButton("9:00 PM", callback_data="time_09:00_PM"),
            InlineKeyboardButton("10:00 PM", callback_data="time_10:00_PM"),
            InlineKeyboardButton("Custom Time", callback_data="time_custom")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "⏰ Choose a time to schedule messages:\n\n"
        "Select from the options below or choose 'Custom Time' to enter your own:",
        reply_markup=reply_markup
    )

async def handle_time_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle time selection from inline keyboard"""
    global scheduled_messages, scheduled_time, target_chat_id, is_scheduling_active, current_message_index, user_states
    
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if query.data.startswith("time_"):
        if query.data == "time_custom":
            # Ask for custom time input
            user_states[user_id] = {'step': 'awaiting_custom_time'}
            await query.edit_message_text(
                "⏰ Please enter your custom time in 12-hour format:\n\n"
                "Examples:\n"
                "• 2:30 PM\n"
                "• 11:45 AM\n"
                "• 6:15 PM\n\n"
                "Type your time now:"
            )
            return
        
        # Extract time from callback data
        time_str = query.data.replace("time_", "").replace("_", ":")
        parsed_time = parse_time(time_str)
        
        if parsed_time:
            await setup_scheduling(query, context, parsed_time, time_str)
        else:
            await query.edit_message_text("❌ Error parsing time. Please try again with /schedule")

async def handle_custom_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom time input from user"""
    global user_states
    
    user_id = update.effective_user.id
    
    if user_id in user_states and user_states[user_id].get('step') == 'awaiting_custom_time':
        time_str = update.message.text.strip()
        parsed_time = parse_time(time_str)
        
        if parsed_time:
            await setup_scheduling_from_message(update, context, parsed_time, time_str)
            # Clear user state
            del user_states[user_id]
        else:
            await update.message.reply_text(
                "❌ Invalid time format. Please use 12-hour format.\n"
                "Examples: 2:30 PM, 11:45 AM, 6:15 PM\n\n"
                "Try again or use /schedule to restart:"
            )

async def message_scheduler(context):
    """Background task to check and send ALL messages at scheduled time"""
    global scheduled_time, is_scheduling_active, scheduled_messages, target_chat_id
    
    ist = pytz.timezone('Asia/Kolkata')
    
    while is_scheduling_active:
        try:
            now_ist = datetime.now(ist).time()
            
            # Check if it's time to send ALL messages at once
            if (scheduled_time.hour == now_ist.hour and 
                scheduled_time.minute == now_ist.minute and
                len(scheduled_messages) > 0):
                
                print("\n" + "="*80)
                print("🚀 SCHEDULED TIME REACHED! SENDING ALL MESSAGES...")
                print("="*80)
                logger.info(f"Time reached! Sending all {len(scheduled_messages)} messages at once...")
                
                # Send all messages at once
                await send_all_messages_at_once(context)
                
                # Stop scheduling after sending all messages
                is_scheduling_active = False
                
                print("✅ ALL MESSAGES SENT SUCCESSFULLY!")
                print("="*80)
                
                # Wait 60 seconds to avoid triggering again in the same minute
                await asyncio.sleep(60)
            else:
                # Check every 30 seconds
                await asyncio.sleep(30)
                
        except Exception as e:
            logger.error(f"Error in message scheduler: {e}")
            await asyncio.sleep(30)

async def send_all_messages_at_once(context):
    """Send all prepared messages at once when scheduled time arrives"""
    global scheduled_messages, target_chat_id
    
    if not scheduled_messages or not target_chat_id:
        logger.error("No messages or target chat ID found")
        return
    
    successful_sends = 0
    failed_sends = 0
    
    print(f"\n📤 Starting to send {len(scheduled_messages)} messages...")
    logger.info(f"Starting to send {len(scheduled_messages)} messages...")
    
    # Send all messages with small delays to avoid rate limiting
    for i, message in enumerate(scheduled_messages):
        try:
            print(f"📤 Sending message {i + 1}/{len(scheduled_messages)}...")
            
            await context.bot.send_message(
                chat_id=target_chat_id,
                text=message,
                parse_mode='HTML'
            )
            
            successful_sends += 1
            print(f"✅ Message {i + 1} sent successfully")
            logger.info(f"Sent message {i + 1}/{len(scheduled_messages)}")
            
            # Small delay between messages to avoid rate limiting (0.5 seconds)
            if i < len(scheduled_messages) - 1:  # Don't wait after the last message
                await asyncio.sleep(0.5)
                
        except Exception as e:
            failed_sends += 1
            print(f"❌ Failed to send message {i + 1}: {e}")
            logger.error(f"Failed to send message {i + 1}: {e}")
            # Continue sending other messages even if one fails
            await asyncio.sleep(1)  # Wait a bit longer on error
    
    # Print summary in terminal
    print(f"\n📊 DELIVERY SUMMARY:")
    print(f"✅ Successfully sent: {successful_sends}")
    print(f"❌ Failed to send: {failed_sends}")
    print(f"📊 Total: {len(scheduled_messages)}")
    
    # Send completion summary to chat
    try:
        summary_message = (
            f"📋 **Message Delivery Complete!**\n\n"
            f"✅ Successfully sent: {successful_sends}\n"
            f"❌ Failed to send: {failed_sends}\n"
            f"📊 Total: {len(scheduled_messages)}"
        )
        
        await context.bot.send_message(
            chat_id=target_chat_id,
            text=summary_message,
            parse_mode='Markdown'
        )
        
        logger.info(f"All messages sent! Success: {successful_sends}, Failed: {failed_sends}")
        
    except Exception as e:
        logger.error(f"Failed to send summary message: {e}")

async def setup_scheduling(query, context, parsed_time, time_str):
    """Set up message scheduling (for inline keyboard selection)"""
    global scheduled_messages, scheduled_time, target_chat_id, is_scheduling_active, current_message_index
    
    print("\n" + "="*80)
    print("⏰ SETTING UP MESSAGE SCHEDULING...")
    print("="*80)
    
    # Load and prepare all messages from file
    messages = load_messages_from_file()
    if not messages:
        await query.edit_message_text("❌ No messages found in messages_to_user.txt file.")
        return
    
    # Set up scheduling variables
    scheduled_messages = messages
    scheduled_time = parsed_time
    target_chat_id = query.message.chat_id
    current_message_index = 0
    is_scheduling_active = True
    
    # Convert to IST for display
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)
    scheduled_datetime = now_ist.replace(
        hour=parsed_time.hour,
        minute=parsed_time.minute,
        second=0,
        microsecond=0
    )
    
    # If the time has passed today, schedule for tomorrow
    if scheduled_datetime <= now_ist:
        scheduled_datetime = scheduled_datetime.replace(day=scheduled_datetime.day + 1)
    
    print(f"📰 Total messages prepared: {len(messages)}")
    print(f"⏰ Scheduled time: {time_str} IST")
    print(f"📅 Send date: {scheduled_datetime.strftime('%Y-%m-%d')}")
    print(f"🎯 Target chat ID: {target_chat_id}")
    print("✅ SCHEDULING SETUP COMPLETE!")
    print("="*80)
    
    await query.edit_message_text(
        f"✅ **Messages Prepared & Scheduled!**\n\n"
        f"📰 Total messages ready: **{len(messages)}**\n"
        f"⏰ Scheduled time: **{time_str} IST**\n"
        f"📅 Send date: **{scheduled_datetime.strftime('%Y-%m-%d')}**\n"
        f"🚀 All messages will be sent **at once** when time arrives!\n\n"
        f"Use /stop to cancel scheduling."
    )
    
    logger.info(f"Scheduled {len(messages)} messages for {time_str} IST")
    
    # Start the scheduling loop
    asyncio.create_task(message_scheduler(context))

async def setup_scheduling_from_message(update, context, parsed_time, time_str):
    """Set up message scheduling (for custom time input)"""
    global scheduled_messages, scheduled_time, target_chat_id, is_scheduling_active, current_message_index
    
    print("\n" + "="*80)
    print("⏰ SETTING UP MESSAGE SCHEDULING (CUSTOM TIME)...")
    print("="*80)
    
    # Load and prepare all messages from file
    messages = load_messages_from_file()
    if not messages:
        await update.message.reply_text("❌ No messages found in messages_to_user.txt file.")
        return
    
    # Set up scheduling variables
    scheduled_messages = messages
    scheduled_time = parsed_time
    target_chat_id = update.effective_chat.id
    current_message_index = 0
    is_scheduling_active = True
    
    # Convert to IST for display
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist)
    scheduled_datetime = now_ist.replace(
        hour=parsed_time.hour,
        minute=parsed_time.minute,
        second=0,
        microsecond=0
    )
    
    # If the time has passed today, schedule for tomorrow
    if scheduled_datetime <= now_ist:
        scheduled_datetime = scheduled_datetime.replace(day=scheduled_datetime.day + 1)
    
    print(f"📰 Total messages prepared: {len(messages)}")
    print(f"⏰ Scheduled time: {time_str} IST")
    print(f"📅 Send date: {scheduled_datetime.strftime('%Y-%m-%d')}")
    print(f"🎯 Target chat ID: {target_chat_id}")
    print("✅ SCHEDULING SETUP COMPLETE!")
    print("="*80)
    
    await update.message.reply_text(
        f"✅ **Messages Prepared & Scheduled!**\n\n"
        f"📰 Total messages ready: **{len(messages)}**\n"
        f"⏰ Scheduled time: **{time_str} IST**\n"
        f"📅 Send date: **{scheduled_datetime.strftime('%Y-%m-%d')}**\n"
        f"🚀 All messages will be sent **at once** when time arrives!\n\n"
        f"Use /stop to cancel scheduling."
    )
    
    logger.info(f"Scheduled {len(messages)} messages for {time_str} IST")
    
    # Start the scheduling loop
    asyncio.create_task(message_scheduler(context))

async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check scheduling status"""
    global is_scheduling_active, scheduled_messages, scheduled_time
    
    if is_scheduling_active:
        ist = pytz.timezone('Asia/Kolkata')
        now_ist = datetime.now(ist)
        scheduled_datetime = now_ist.replace(
            hour=scheduled_time.hour,
            minute=scheduled_time.minute,
            second=0,
            microsecond=0
        )
        
        # If the time has passed today, it's scheduled for tomorrow
        if scheduled_datetime <= now_ist:
            scheduled_datetime = scheduled_datetime.replace(day=scheduled_datetime.day + 1)
        
        time_remaining = scheduled_datetime - now_ist
        hours, remainder = divmod(time_remaining.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        # Print status in terminal too
        print(f"\n📊 CURRENT SCHEDULING STATUS:")
        print(f"✅ Active - {len(scheduled_messages)} messages ready")
        print(f"⏰ Time: {scheduled_time.strftime('%I:%M %p')} IST")
        print(f"⏳ Time remaining: {hours}h {minutes}m")
        
        await update.message.reply_text(
            f"📊 **Scheduling Status**\n\n"
            f"✅ **Active**\n"
            f"📰 Messages prepared: **{len(scheduled_messages)}**\n"
            f"⏰ Scheduled time: **{scheduled_time.strftime('%I:%M %p')} IST**\n"
            f"📅 Send date: **{scheduled_datetime.strftime('%Y-%m-%d')}**\n"
            f"⏳ Time remaining: **{hours}h {minutes}m**\n\n"
            f"🚀 All messages will be sent at once when time arrives!"
        )
    else:
        print("📊 No active scheduling")
        await update.message.reply_text("📊 No active scheduling")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    user_id = update.effective_user.id
    
    # Check if user is in custom time input mode
    if user_id in user_states and user_states[user_id].get('step') == 'awaiting_custom_time':
        await handle_custom_time_input(update, context)
        return
    
    logger.info(f"Received message from {update.effective_user.first_name}: {user_input}")
    
    try:
        # Send "typing" indicator to show bot is processing
        await update.message.chat.send_action("typing")
        
        # Create streaming completion with user's actual input
        stream = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are CurateX AI, a helpful and knowledgeable assistant. Provide clear, accurate, and helpful responses."
                },
                {
                    "role": "user",
                    "content": user_input
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_completion_tokens=1024,
            top_p=1,
            stream=True,
        )
        
        # Collect the streaming response
        response_text = ""
        for chunk in stream:
            if chunk.choices[0].delta.content:
                response_text += chunk.choices[0].delta.content
        
        # Send the complete response
        await update.message.reply_text(response_text)
        logger.info("Response sent successfully")
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await update.message.reply_text("Sorry, I encountered an error while processing your request. Please try again.")

async def stop_scheduling(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop scheduled messages"""
    global is_scheduling_active, scheduled_messages, scheduled_time, target_chat_id
    
    if is_scheduling_active:
        is_scheduling_active = False
        
        # Print stop notification in terminal
        print("\n" + "="*80)
        print("🛑 SCHEDULING STOPPED BY USER")
        print("="*80)
        print(f"📰 Messages that were scheduled: {len(scheduled_messages)}")
        if scheduled_time:
            print(f"⏰ Original scheduled time: {scheduled_time.strftime('%I:%M %p')} IST")
        print("✅ SCHEDULING CANCELLED SUCCESSFULLY")
        print("="*80)
        
        # Clear scheduling variables
        scheduled_messages = []
        scheduled_time = None
        target_chat_id = None
        
        await update.message.reply_text(
            "❌ **Scheduled messages stopped.**\n\n"
            "All pending message deliveries have been cancelled.\n"
            "Use /schedule to set up new scheduling."
        )
        
        logger.info("Scheduling stopped by user")
    else:
        print("📊 No active scheduling to stop")
        await update.message.reply_text("📊 No active scheduling to stop.")

def main():
    print("="*80)
    print("🤖 STARTING CURATEX AI BOT...")
    print("="*80)
    print("Bot is running! Press Ctrl+C to stop.")
    print("Terminal will show message previews when scheduling is set up.")
    print("="*80)
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("schedule", schedule_messages))
    app.add_handler(CommandHandler("stop", stop_scheduling))  # Now this will work
    app.add_handler(CommandHandler("status", check_status))
    app.add_handler(CallbackQueryHandler(handle_time_selection))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    try:
        app.run_polling()
    except KeyboardInterrupt:
        print("\n" + "="*80)
        print("🛑 BOT STOPPED BY USER")
        print("="*80)
    except Exception as e:
        logger.error(f"Bot error: {e}")

if __name__ == "__main__":
    main()