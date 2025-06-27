from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import os
import dotenv as env
import logging
from groq import Groq

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"User {update.effective_user.first_name} started the bot")
    await update.message.reply_text("Hi! I'm your CurateX AI bot. Ask me anything!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
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

def main():
    print("Starting CurateX AI Bot...")
    print("Bot is running! Press Ctrl+C to stop.")
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    try:
        app.run_polling()
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        logger.error(f"Bot error: {e}")

if __name__ == "__main__":
    main()


