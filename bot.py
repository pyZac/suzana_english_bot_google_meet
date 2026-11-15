#!/usr/bin/env python3
"""
Suzana English Learning Bot
Main bot file with registration system
"""

import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)

import config
from database import DatabaseHandler
from registration import RegistrationHandler, ENGLISH_LEVEL, PHONE_NUMBER, STUDENT_FIELD, PACKAGE_TYPE
from invoice_handler import InvoiceHandler
from group_manager import GroupManager
from meet_scheduler import MeetScheduler
import asyncio

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize database
db = DatabaseHandler()

# Initialize registration handler
registration_handler = RegistrationHandler(db)

# Invoice handler and meet scheduler will be initialized in main() with group_manager
invoice_handler = None
meet_scheduler = None


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - begin registration"""
    return await registration_handler.start_registration(update, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
🤖 **Suzana English Learning Bot - Help**

**Available Commands:**
/start - Start registration process
/help - Show this help message
/status - Check your subscription status
/cancel - Cancel current operation

**How to use:**
1️⃣ Start with /start to register
2️⃣ Answer the questions about your English level, field, and package
3️⃣ Send your payment invoice (screenshot/photo)
4️⃣ Get added to your learning group automatically!

**Need assistance?**
Contact Suzana directly for any questions.
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command - check subscription status"""
    user = update.effective_user
    
    # Get member status from database
    status = db.get_member_status(user.id)
    
    if status:
        expiration_date = status['expiration_date'].strftime('%Y-%m-%d')
        days_left = (status['expiration_date'] - status['payment_date']).days
        
        message = f"""
✅ **Your Subscription Status**

👤 **Name:** {user.first_name}
📚 **English Level:** {status.get('british_council_score', 'Not specified')}
📅 **Expires on:** {expiration_date}
⏰ **Days remaining:** {days_left} days

Your subscription is **active**! 🎉
        """
    else:
        message = """
⚠️ **No Active Subscription**

You don't have an active subscription yet.

Please send your payment invoice to activate your subscription!
        """
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def income_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /income command - show monthly income report (admin only)"""
    user = update.effective_user
    
    # Check if user is admin
    if user.id not in config.ADMIN_USER_IDS:
        await update.message.reply_text("⛔ This command is only available to administrators.")
        return
    
    # Get month from command args (optional)
    month_year = None
    if context.args:
        month_year = context.args[0]  # Format: YYYY-MM (e.g., 2025-11)
    
    # Get income report
    report = db.get_monthly_income_report(month_year)
    
    if not report:
        await update.message.reply_text("❌ Error generating income report.")
        return
    
    # Format the report
    message = f"💰 **Income Report - {report['month_year']}**\n\n"
    
    if report['by_package']:
        for pkg in report['by_package']:
            package_name = pkg['package_type'] or 'Unknown'
            count = pkg['payment_count']
            amount = pkg['total_amount'] or 0
            message += f"📦 **{package_name}:**\n"
            message += f"   • Payments: {count}\n"
            message += f"   • Total: {amount:,.0f} SYP\n\n"
        
        message += f"**━━━━━━━━━━━━━━**\n"
        message += f"💵 **Total Income:** {report['total_income']:,.0f} SYP"
    else:
        message += "No payments recorded for this month."
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo messages (invoices)"""
    await invoice_handler.process_invoice(update, context)


async def register_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Register a Telegram group (admin only) - Usage: /registergroup <type> <level> <package>"""
    user = update.effective_user
    
    # Check if user is admin
    if user.id not in config.ADMIN_USER_IDS:
        await update.message.reply_text("⛔ This command is only available to administrators.")
        return
    
    # Check if command is used in a group
    if update.effective_chat.type == 'private':
        await update.message.reply_text(
            "❌ This command must be used inside the group you want to register!\n\n"
            "**Usage:**\n"
            "For general group: `/registergroup general`\n"
            "For class: `/registergroup class A IELTS`\n"
            "For class: `/registergroup class B Speaking`",
            parse_mode='Markdown'
        )
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "**Usage:**\n"
            "For general group: `/registergroup general`\n"
            "For class: `/registergroup class <level> <package>`\n\n"
            "Example: `/registergroup class A IELTS`",
            parse_mode='Markdown'
        )
        return
    
    group_type = context.args[0].lower()
    group_id = update.effective_chat.id
    group_name = update.effective_chat.title
    
    # Initialize group_manager if needed
    from group_manager import GroupManager
    gm = GroupManager(db, context.bot)
    
    if group_type == 'general':
        # Register general group
        if gm.register_group(group_id, 'general', group_name):
            await update.message.reply_text(
                f"✅ **General group registered successfully!**\n\n"
                f"📛 Group: {group_name}\n"
                f"🆔 ID: `{group_id}`\n\n"
                f"This is now the main community group.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Error registering group.")
    
    elif group_type == 'class':
        if len(context.args) < 3:
            await update.message.reply_text(
                "❌ Please specify level and package!\n\n"
                "**Usage:** `/registergroup class <level> <package>`\n"
                "Example: `/registergroup class A IELTS`",
                parse_mode='Markdown'
            )
            return
        
        level_category = context.args[1].upper()
        package_type = context.args[2]
        
        # Validate level
        if level_category not in ['A', 'B', 'C']:
            await update.message.reply_text("❌ Level must be A, B, or C")
            return
        
        # Validate package
        if package_type not in ['IELTS', 'Speaking']:
            await update.message.reply_text("❌ Package must be IELTS or Speaking")
            return
        
        # Register class
        if gm.register_group(group_id, 'class', group_name, level_category, package_type):
            await update.message.reply_text(
                f"✅ **Class registered successfully!**\n\n"
                f"📛 Group: {group_name}\n"
                f"🆔 ID: `{group_id}`\n"
                f"📚 Level: {level_category}\n"
                f"📦 Package: {package_type}\n\n"
                f"Students will be automatically assigned to this class.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Error registering group.")
    
    else:
        await update.message.reply_text("❌ Type must be 'general' or 'class'")


async def schedule_class_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Schedule a recurring class with Google Meet (admin only)
    Usage: /scheduleclass <package> <level> <day> <time>
    Example: /scheduleclass IELTS A Monday 18:00
    """
    user = update.effective_user
    
    # Check if user is admin
    if user.id not in config.ADMIN_USER_IDS:
        await update.message.reply_text("⛔ This command is only available to administrators.")
        return
    
    if not context.args or len(context.args) < 4:
        await update.message.reply_text(
            "**📅 Schedule a Recurring Class**\n\n"
            "**Usage:** `/scheduleclass <package> <level> <day> <time>`\n\n"
            "**Examples:**\n"
            "`/scheduleclass IELTS A Monday 18:00`\n"
            "`/scheduleclass Speaking B Wednesday 19:30`\n\n"
            "**Parameters:**\n"
            "• Package: IELTS or Speaking\n"
            "• Level: A, B, or C\n"
            "• Day: Monday-Sunday\n"
            "• Time: 24h format (e.g., 18:00)",
            parse_mode='Markdown'
        )
        return
    
    package_type = context.args[0]
    level_category = context.args[1].upper()
    day_of_week = context.args[2].capitalize()
    time_str = context.args[3]
    
    # Validate inputs
    valid_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    if package_type not in ['IELTS', 'Speaking']:
        await update.message.reply_text("❌ Package must be IELTS or Speaking")
        return
    
    if level_category not in ['A', 'B', 'C']:
        await update.message.reply_text("❌ Level must be A, B, or C")
        return
    
    if day_of_week not in valid_days:
        await update.message.reply_text("❌ Day must be Monday-Sunday")
        return
    
    # Validate time format
    try:
        hour, minute = map(int, time_str.split(':'))
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError
    except:
        await update.message.reply_text("❌ Time must be in 24h format (e.g., 18:00)")
        return
    
    # Schedule the class
    schedule_id = meet_scheduler.schedule_class(
        package_type=package_type,
        level_category=level_category,
        day_of_week=day_of_week,
        time_str=time_str,
        duration_minutes=90
    )
    
    if schedule_id:
        await update.message.reply_text(
            f"✅ **Class Scheduled Successfully!**\n\n"
            f"📦 **Package:** {package_type}\n"
            f"📚 **Level:** {level_category}\n"
            f"📅 **Day:** {day_of_week}\n"
            f"🕐 **Time:** {time_str}\n"
            f"⏱️ **Duration:** 90 minutes\n\n"
            f"🤖 Google Meet links will be sent automatically 30 minutes before each class!",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Error scheduling class. Please try again.")


async def list_schedules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all scheduled classes (admin only)"""
    user = update.effective_user
    
    # Check if user is admin
    if user.id not in config.ADMIN_USER_IDS:
        await update.message.reply_text("⛔ This command is only available to administrators.")
        return
    
    schedules = meet_scheduler.get_active_schedules()
    
    if not schedules:
        await update.message.reply_text("📅 No classes scheduled yet.")
        return
    
    message = "📅 **Scheduled Classes:**\n\n"
    
    for schedule in schedules:
        message += (
            f"🆔 ID: {schedule['id']}\n"
            f"📦 {schedule['package_type']} - Level {schedule['level_category']}\n"
            f"📅 {schedule['day_of_week']} at {schedule['time']}\n"
            f"⏱️ Duration: {schedule['duration_minutes']} min\n\n"
        )
    
    message += "\n💡 Use `/deleteschedule <id>` to remove a schedule"
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def delete_schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a scheduled class (admin only)
    Usage: /deleteschedule <id>
    """
    user = update.effective_user
    
    # Check if user is admin
    if user.id not in config.ADMIN_USER_IDS:
        await update.message.reply_text("⛔ This command is only available to administrators.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "**Usage:** `/deleteschedule <id>`\n\n"
            "Use `/listschedules` to see all schedule IDs",
            parse_mode='Markdown'
        )
        return
    
    try:
        schedule_id = int(context.args[0])
    except:
        await update.message.reply_text("❌ Schedule ID must be a number")
        return
    
    if meet_scheduler.delete_schedule(schedule_id):
        await update.message.reply_text(
            f"✅ Schedule #{schedule_id} deleted successfully!"
        )
    else:
        await update.message.reply_text("❌ Error deleting schedule. Please check the ID.")


async def register_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Register a Telegram group (admin only) - Usage: /registergroup <type> <level> <package>"""
    user = update.effective_user
    
    # Check if user is admin
    if user.id not in config.ADMIN_USER_IDS:
        await update.message.reply_text("⛔ This command is only available to administrators.")
        return
    
    # Check if command is used in a group
    if update.effective_chat.type == 'private':
        await update.message.reply_text(
            "❌ This command must be used inside the group you want to register!\n\n"
            "**Usage:**\n"
            "For general group: `/registergroup general`\n"
            "For class: `/registergroup class A IELTS`\n"
            "For class: `/registergroup class B Speaking`",
            parse_mode='Markdown'
        )
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "**Usage:**\n"
            "For general group: `/registergroup general`\n"
            "For class: `/registergroup class <level> <package>`\n\n"
            "Example: `/registergroup class A IELTS`",
            parse_mode='Markdown'
        )
        return
    
    group_type = context.args[0].lower()
    group_id = update.effective_chat.id
    group_name = update.effective_chat.title
    
    # Initialize group_manager if needed
    from group_manager import GroupManager
    gm = GroupManager(db, context.bot)
    
    if group_type == 'general':
        # Register general group
        if gm.register_group(group_id, 'general', group_name):
            await update.message.reply_text(
                f"✅ **General group registered successfully!**\n\n"
                f"📛 Group: {group_name}\n"
                f"🆔 ID: `{group_id}`\n\n"
                f"This is now the main community group.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Error registering group.")
    
    elif group_type == 'class':
        if len(context.args) < 3:
            await update.message.reply_text(
                "❌ Please specify level and package!\n\n"
                "**Usage:** `/registergroup class <level> <package>`\n"
                "Example: `/registergroup class A IELTS`",
                parse_mode='Markdown'
            )
            return
        
        level_category = context.args[1].upper()
        package_type = context.args[2]
        
        # Validate level
        if level_category not in ['A', 'B', 'C']:
            await update.message.reply_text("❌ Level must be A, B, or C")
            return
        
        # Validate package
        if package_type not in ['IELTS', 'Speaking']:
            await update.message.reply_text("❌ Package must be IELTS or Speaking")
            return
        
        # Register class
        if gm.register_group(group_id, 'class', group_name, level_category, package_type):
            await update.message.reply_text(
                f"✅ **Class registered successfully!**\n\n"
                f"📛 Group: {group_name}\n"
                f"🆔 ID: `{group_id}`\n"
                f"📚 Level: {level_category}\n"
                f"📦 Package: {package_type}\n\n"
                f"Students will be automatically assigned to this class.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Error registering group.")
    
    else:
        await update.message.reply_text("❌ Type must be 'general' or 'class'")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An error occurred. Please try again or contact support."
        )


async def check_scheduled_classes_job(context: ContextTypes.DEFAULT_TYPE):
    """Background job to check and send Google Meet links"""
    try:
        await meet_scheduler.process_scheduled_classes()
    except Exception as e:
        logger.error(f"Error in scheduled classes job: {e}")


def main():
    """Start the bot"""
    
    # Connect to database
    if not db.connect():
        logger.error("Failed to connect to database. Exiting.")
        return
    
    # Create tables if they don't exist
    if not db.create_tables():
        logger.error("Failed to create database tables. Exiting.")
        return
    
    logger.info("Database connected and tables ready")
    
    # Create application
    application = Application.builder().token(config.BOT_TOKEN).build()
    
    # Initialize group manager with bot instance
    group_manager = GroupManager(db, application.bot)
    
    # Initialize invoice handler with group manager
    global invoice_handler
    invoice_handler = InvoiceHandler(db, group_manager)
    
    # Initialize Google Meet scheduler
    global meet_scheduler
    meet_scheduler = MeetScheduler(
        db_handler=db,
        bot=application.bot,
        credentials_file=config.GOOGLE_CREDENTIALS_FILE
    )
    
    # Add background job to check scheduled classes every 15 minutes
    job_queue = application.job_queue
    job_queue.run_repeating(
        check_scheduled_classes_job,
        interval=900,  # 15 minutes in seconds
        first=10  # Start after 10 seconds
    )
    
    # Registration conversation handler
    registration_conv = ConversationHandler(
        entry_points=[CommandHandler('start', start_command)],
        states={
            ENGLISH_LEVEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, registration_handler.receive_english_level)
            ],
            PHONE_NUMBER: [
                MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), registration_handler.receive_phone_number)
            ],
            STUDENT_FIELD: [
                CallbackQueryHandler(registration_handler.receive_student_field, pattern='^field_')
            ],
            PACKAGE_TYPE: [
                CallbackQueryHandler(registration_handler.receive_package_type, pattern='^package_')
            ],
        },
        fallbacks=[CommandHandler('cancel', registration_handler.cancel_registration)],
        allow_reentry=True
    )
    
    # Add handlers
    application.add_handler(registration_conv)
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('status', status_command))
    application.add_handler(CommandHandler('income', income_command))
    application.add_handler(CommandHandler('registergroup', register_group_command))
    application.add_handler(CommandHandler('scheduleclass', schedule_class_command))
    application.add_handler(CommandHandler('listschedules', list_schedules_command))
    application.add_handler(CommandHandler('deleteschedule', delete_schedule_command))
    
    # Add photo handler for invoices (outside conversation handler)
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    
    # Close database connection when done
    db.close()


if __name__ == '__main__':
    main()