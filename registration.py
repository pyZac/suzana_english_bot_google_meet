from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

# Conversation states
ENGLISH_LEVEL, PHONE_NUMBER, STUDENT_FIELD, PACKAGE_TYPE = range(4)

# British Council Test Link
BRITISH_COUNCIL_LINK = "https://learnenglish.britishcouncil.org/online-english-level-test"

class RegistrationHandler:
    def __init__(self, db_handler):
        self.db = db_handler
    
    async def start_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start the registration process"""
        user = update.effective_user
        
        # Add member to database
        self.db.add_member(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        # Ask first question about English level
        message = (
            f"👋 Welcome {user.first_name}! I'm Suzana's English Learning Assistant.\n\n"
            "Let me ask you a few questions to help us place you in the right group.\n\n"
            "📝 **Question 1 of 4:**\n\n"
            "🎯 What is your English level?\n\n"
            "Please take the British Council English Level Test first if you haven't already:\n"
            f"🔗 {BRITISH_COUNCIL_LINK}\n\n"
            "Then reply with your level: **A1, A2, B1, B2, C1, or C2**"
        )
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
        return ENGLISH_LEVEL
    
    async def receive_english_level(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive and store English level"""
        user = update.effective_user
        british_council_score = update.message.text.strip().upper()
        
        # Validate the score
        valid_scores = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
        if british_council_score not in valid_scores:
            await update.message.reply_text(
                "❌ Please enter a valid British Council level: A1, A2, B1, B2, C1, or C2"
            )
            return ENGLISH_LEVEL
        
        # Store in database
        self.db.update_british_council_score(user.id, british_council_score)
        
        # Store in context for later use
        context.user_data['british_council_score'] = british_council_score
        
        # Ask for phone number
        message = (
            f"✅ Great! Your English level is: **{british_council_score}**\n\n"
            "📝 **Question 2 of 4:**\n\n"
            "📱 Please share your phone number.\n\n"
            "You can either:\n"
            "• Click the button below to share it automatically, or\n"
            "• Type it manually (e.g., +963 123 456 789)"
        )
        
        # Create keyboard with contact sharing button
        from telegram import KeyboardButton, ReplyKeyboardMarkup
        keyboard = [[KeyboardButton("📱 Share Phone Number", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        
        return PHONE_NUMBER
    
    async def receive_phone_number(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive and store phone number"""
        user = update.effective_user
        
        # Check if user shared contact
        if update.message.contact:
            phone_number = update.message.contact.phone_number
        # Or typed it manually
        elif update.message.text:
            phone_number = update.message.text.strip()
        else:
            await update.message.reply_text("❌ Please share your phone number or type it.")
            return PHONE_NUMBER
        
        # Store in database
        self.db.update_phone_number(user.id, phone_number)
        
        # Store in context
        context.user_data['phone_number'] = phone_number
        
        # Ask third question with buttons (student field)
        keyboard = [
            [InlineKeyboardButton("🏗️ Civil Engineering Student", callback_data='field_civil')],
            [InlineKeyboardButton("🏛️ Architecture Student", callback_data='field_architecture')],
            [InlineKeyboardButton("⚕️ Medical Field Student", callback_data='field_medical')],
            [InlineKeyboardButton("📚 Other", callback_data='field_other')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Remove the phone number keyboard
        from telegram import ReplyKeyboardRemove
        
        message = (
            f"✅ Phone number saved: **{phone_number}**\n\n"
            "📝 **Question 3 of 4:**\n\n"
            "🎓 What field are you studying or working in?\n\n"
            "Please select one of the options below:"
        )
        
        await update.message.reply_text(
            message, 
            reply_markup=reply_markup, 
            parse_mode='Markdown'
        )
        
        return STUDENT_FIELD
    
    async def receive_student_field(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive and store student field from button callback"""
        query = update.callback_query
        await query.answer()
        
        user = query.from_user
        
        # Parse the callback data
        field_map = {
            'field_civil': 'Civil Engineering',
            'field_architecture': 'Architecture',
            'field_medical': 'Medical Field',
            'field_other': 'Other'
        }
        
        student_field = field_map.get(query.data, 'Other')
        
        # Store in database
        self.db.update_member_field(user.id, student_field)
        
        # Store in context
        context.user_data['student_field'] = student_field
        
        # Ask fourth question about package with detailed descriptions
        keyboard = [
            [InlineKeyboardButton("🎓 IELTS Package", callback_data='package_ielts')],
            [InlineKeyboardButton("💬 Speaking Package", callback_data='package_speaking')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            f"✅ Thank you! Field recorded: **{student_field}**\n\n"
            "📝 **Question 4 of 4:**\n\n"
            "📦 Which learning package would you like?\n\n"
            "**🎓 IELTS Package:**\n"
            "• Complete IELTS preparation (Reading, Writing, Listening, Speaking)\n"
            "• Practice tests and mock exams\n"
            "• Score improvement strategies\n"
            "• Exam tips and techniques\n"
            "• 8 sessions per month\n\n"
            "**💬 Speaking Package:**\n"
            "• Focus on conversation and fluency\n"
            "• Pronunciation improvement\n"
            "• Real-life scenarios practice\n"
            "• Vocabulary building\n"
            "• 6 sessions per month\n\n"
            "Please select your preferred package:"
        )
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        
        return PACKAGE_TYPE
    
    async def receive_package_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive and store package type, complete registration"""
        query = update.callback_query
        await query.answer()
        
        user = query.from_user
        
        # Parse the callback data - CHANGED: Now storing just "IELTS" and "Speaking"
        package_map = {
            'package_ielts': 'IELTS',
            'package_speaking': 'Speaking'
        }
        
        package_type = package_map.get(query.data, 'IELTS')
        
        # Store in database
        self.db.update_member_package(user.id, package_type)
        
        # Get all stored data
        british_council_score = context.user_data.get('british_council_score', 'Not specified')
        phone_number = context.user_data.get('phone_number', 'Not specified')
        student_field = context.user_data.get('student_field', 'Not specified')
        
        # For display purposes, add "Package" back
        display_package = f"{package_type} Package"
        
        # Send completion message
        message = (
            "✅ **Registration Complete!**\n\n"
            "📋 Your profile:\n"
            f"• **English Level:** {british_council_score}\n"
            f"• **Phone:** {phone_number}\n"
            f"• **Field:** {student_field}\n"
            f"• **Package:** {display_package}\n\n"
            "🎉 Welcome to Suzana's English Learning Community!\n\n"
            "💳 **Next Step:** Please send your **Sham Cash** payment invoice so we can activate your subscription.\n\n"
            "📸 Send a screenshot or photo of your payment receipt, and I'll verify it for you!"
        )
        
        await query.edit_message_text(message, parse_mode='Markdown')
        
        # Clear context data
        context.user_data.clear()
        
        return ConversationHandler.END
    
    async def cancel_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel the registration process"""
        await update.message.reply_text(
            "Registration cancelled. Type /start to begin again."
        )
        return ConversationHandler.END