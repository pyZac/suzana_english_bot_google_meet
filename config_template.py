"""
Configuration file for Suzana English Learning Bot
IMPORTANT: Copy this to config.py and fill in your actual values
"""

# Telegram Bot Token
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# Admin User IDs (can use multiple commands)
ADMIN_USER_IDs = [
    6233703198,  # Developer
    926422038    # Suzana
]

# MySQL Database Configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'your_mysql_user',
    'password': 'your_mysql_password',
    'database': 'suzana_english'
}

# Payment Configuration
SUBSCRIPTION_DURATION_DAYS = 30  # How long subscription lasts
REMINDER_DAYS_BEFORE = 3  # Remind X days before expiration

# Expected payment receiver name (for invoice verification)
EXPECTED_RECEIVER = "firasraslan"

# Google Calendar API Credentials
# Path to your Google service account credentials JSON file
GOOGLE_CREDENTIALS_FILE = "/path/to/your/google-credentials.json"
