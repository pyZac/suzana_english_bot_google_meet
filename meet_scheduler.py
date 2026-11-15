"""
Google Meet Scheduler
Handles automatic creation and distribution of Google Meet links for classes
"""

from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pytz

class MeetScheduler:
    def __init__(self, db_handler, bot, credentials_file):
        """
        Initialize Meet Scheduler
        
        Args:
            db_handler: Database handler instance
            bot: Telegram bot instance
            credentials_file: Path to Google service account credentials JSON
        """
        self.db = db_handler
        self.bot = bot
        self.credentials_file = credentials_file
        self.service = None
        self.timezone = pytz.timezone('Asia/Damascus')  # Syria timezone
        
        # Initialize Google Calendar API
        self._init_calendar_service()
    
    def _init_calendar_service(self):
        """Initialize Google Calendar API service"""
        try:
            # Define the scopes
            SCOPES = ['https://www.googleapis.com/auth/calendar']
            
            # Load credentials from service account file
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_file,
                scopes=SCOPES
            )
            
            # Build the service
            self.service = build('calendar', 'v3', credentials=credentials)
            print("✅ Google Calendar service initialized successfully")
            
        except Exception as e:
            print(f"❌ Error initializing Google Calendar service: {e}")
            self.service = None
    
    def create_meet_link(self, class_type, level_category, package_type, scheduled_time, duration_minutes=90):
        """
        Create a Google Meet link for a class
        
        Args:
            class_type: Type of class (e.g., 'IELTS', 'Speaking')
            level_category: Level category ('A', 'B', 'C')
            package_type: Package type ('IELTS', 'Speaking')
            scheduled_time: datetime object for when class starts
            duration_minutes: Duration of the class in minutes
            
        Returns:
            dict with meet_link, event_id, or None if failed
        """
        if not self.service:
            print("❌ Google Calendar service not initialized")
            return None
        
        try:
            # Calculate end time
            end_time = scheduled_time + timedelta(minutes=duration_minutes)
            
            # Create event
            event = {
                'summary': f'{package_type} Class - Level {level_category}',
                'description': f'Suzana English Learning - {package_type} class for level {level_category} students',
                'start': {
                    'dateTime': scheduled_time.isoformat(),
                    'timeZone': 'Asia/Damascus',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'Asia/Damascus',
                },
                'conferenceData': {
                    'createRequest': {
                        'requestId': f'suzana-{package_type}-{level_category}-{int(scheduled_time.timestamp())}',
                        'conferenceSolutionKey': {
                            'type': 'hangoutsMeet'
                        }
                    }
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': 30},
                        {'method': 'popup', 'minutes': 10},
                    ],
                },
            }
            
            # Create the event with conferenceData
            created_event = self.service.events().insert(
                calendarId='primary',
                body=event,
                conferenceDataVersion=1
            ).execute()
            
            # Extract Meet link
            meet_link = created_event.get('hangoutLink')
            event_id = created_event.get('id')
            
            if meet_link:
                print(f"✅ Created Meet link for {package_type} Level {level_category}: {meet_link}")
                return {
                    'meet_link': meet_link,
                    'event_id': event_id,
                    'scheduled_time': scheduled_time,
                    'end_time': end_time
                }
            else:
                print("❌ No Meet link in created event")
                return None
                
        except HttpError as error:
            print(f"❌ Google Calendar API error: {error}")
            return None
        except Exception as e:
            print(f"❌ Error creating Meet link: {e}")
            return None
    
    def schedule_class(self, package_type, level_category, day_of_week, time_str, duration_minutes=90):
        """
        Schedule a recurring class
        
        Args:
            package_type: 'IELTS' or 'Speaking'
            level_category: 'A', 'B', or 'C'
            day_of_week: Day name (e.g., 'Monday', 'Tuesday')
            time_str: Time in 24h format (e.g., '18:00', '19:30')
            duration_minutes: Duration of class in minutes
            
        Returns:
            Schedule ID if successful, None otherwise
        """
        try:
            cursor = self.db.connection.cursor()
            
            # Insert into class_schedule table
            query = """
                INSERT INTO class_schedule 
                (package_type, level_category, day_of_week, time, duration_minutes, is_active)
                VALUES (%s, %s, %s, %s, %s, TRUE)
            """
            
            cursor.execute(query, (package_type, level_category, day_of_week, time_str, duration_minutes))
            self.db.connection.commit()
            
            schedule_id = cursor.lastrowid
            print(f"✅ Scheduled {package_type} Level {level_category} class for {day_of_week} at {time_str}")
            
            return schedule_id
            
        except Exception as e:
            print(f"❌ Error scheduling class: {e}")
            return None
    
    def get_next_class_time(self, day_of_week, time_str):
        """
        Get the next occurrence of a specific day and time
        
        Args:
            day_of_week: Day name (e.g., 'Monday')
            time_str: Time in 24h format (e.g., '18:00')
            
        Returns:
            datetime object for next class
        """
        days = {
            'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
            'Friday': 4, 'Saturday': 5, 'Sunday': 6
        }
        
        target_day = days[day_of_week]
        
        # Parse time
        hour, minute = map(int, time_str.split(':'))
        
        # Get current time in Syria timezone
        now = datetime.now(self.timezone)
        
        # Calculate days until next occurrence
        days_ahead = target_day - now.weekday()
        if days_ahead < 0:  # Target day already happened this week
            days_ahead += 7
        elif days_ahead == 0:  # Today - check if time has passed
            target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if now >= target_time:
                days_ahead = 7
        
        # Calculate next class datetime
        next_class = now + timedelta(days=days_ahead)
        next_class = next_class.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        return next_class
    
    async def process_scheduled_classes(self):
        """
        Process all scheduled classes and send Meet links if it's time
        This should be called periodically (e.g., every 15 minutes)
        """
        try:
            cursor = self.db.connection.cursor(dictionary=True)
            
            # Get all active schedules
            cursor.execute("""
                SELECT * FROM class_schedule 
                WHERE is_active = TRUE
            """)
            
            schedules = cursor.fetchall()
            
            for schedule in schedules:
                # Calculate next class time
                next_class_time = self.get_next_class_time(
                    schedule['day_of_week'],
                    schedule['time']
                )
                
                # Check if we should send the link (30 minutes before class)
                now = datetime.now(self.timezone)
                time_until_class = (next_class_time - now).total_seconds() / 60  # in minutes
                
                # Send link if between 30-35 minutes before class
                if 30 <= time_until_class <= 35:
                    # Check if already sent for this class time
                    cursor.execute("""
                        SELECT * FROM meet_links 
                        WHERE schedule_id = %s 
                        AND scheduled_time = %s 
                        AND sent = TRUE
                    """, (schedule['id'], next_class_time))
                    
                    if cursor.fetchone():
                        continue  # Already sent
                    
                    # Create Meet link
                    meet_data = self.create_meet_link(
                        class_type=schedule['package_type'],
                        level_category=schedule['level_category'],
                        package_type=schedule['package_type'],
                        scheduled_time=next_class_time,
                        duration_minutes=schedule['duration_minutes']
                    )
                    
                    if meet_data:
                        # Store in database
                        cursor.execute("""
                            INSERT INTO meet_links 
                            (schedule_id, meet_link, event_id, scheduled_time, sent)
                            VALUES (%s, %s, %s, %s, FALSE)
                        """, (schedule['id'], meet_data['meet_link'], 
                             meet_data['event_id'], next_class_time))
                        self.db.connection.commit()
                        
                        link_id = cursor.lastrowid
                        
                        # Send to appropriate group
                        await self.send_meet_link_to_group(
                            schedule['package_type'],
                            schedule['level_category'],
                            meet_data['meet_link'],
                            next_class_time
                        )
                        
                        # Mark as sent
                        cursor.execute("""
                            UPDATE meet_links SET sent = TRUE 
                            WHERE id = %s
                        """, (link_id,))
                        self.db.connection.commit()
                        
        except Exception as e:
            print(f"❌ Error processing scheduled classes: {e}")
    
    async def send_meet_link_to_group(self, package_type, level_category, meet_link, class_time):
        """
        Send Google Meet link to the appropriate class group
        
        Args:
            package_type: 'IELTS' or 'Speaking'
            level_category: 'A', 'B', or 'C'
            meet_link: Google Meet URL
            class_time: datetime object for class start
        """
        try:
            # Find the group for this class
            cursor = self.db.connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT group_id, group_name FROM telegram_groups 
                WHERE group_type = 'class' 
                AND package_type = %s 
                AND level_category = %s 
                AND is_active = TRUE
                LIMIT 1
            """, (package_type, level_category))
            
            group = cursor.fetchone()
            
            if not group:
                print(f"❌ No group found for {package_type} Level {level_category}")
                return
            
            # Format the message
            time_str = class_time.strftime('%I:%M %p')
            date_str = class_time.strftime('%A, %B %d, %Y')
            
            message = f"""
📹 **Class Starting Soon!**

📚 **Course:** {package_type} - Level {level_category}
🕐 **Time:** {time_str}
📅 **Date:** {date_str}

🔗 **Join the class:**
{meet_link}

⚠️ **Important:**
• Join a few minutes early
• Make sure your camera and microphone work
• This link is for verified members only

See you in class! 👋
"""
            
            # Send to group
            await self.bot.send_message(
                chat_id=group['group_id'],
                text=message,
                parse_mode='Markdown'
            )
            
            print(f"✅ Sent Meet link to {group['group_name']}")
            
        except Exception as e:
            print(f"❌ Error sending Meet link to group: {e}")
    
    def get_active_schedules(self):
        """Get all active class schedules"""
        try:
            cursor = self.db.connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT * FROM class_schedule 
                WHERE is_active = TRUE
                ORDER BY day_of_week, time
            """)
            return cursor.fetchall()
        except Exception as e:
            print(f"❌ Error getting schedules: {e}")
            return []
    
    def delete_schedule(self, schedule_id):
        """Delete a class schedule"""
        try:
            cursor = self.db.connection.cursor()
            cursor.execute("""
                UPDATE class_schedule 
                SET is_active = FALSE 
                WHERE id = %s
            """, (schedule_id,))
            self.db.connection.commit()
            return True
        except Exception as e:
            print(f"❌ Error deleting schedule: {e}")
            return False
