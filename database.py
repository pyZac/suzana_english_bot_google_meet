import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta
import config

class DatabaseHandler:
    def __init__(self):
        self.connection = None
        
    def connect(self):
        """Establish connection to MySQL database"""
        try:
            self.connection = mysql.connector.connect(**config.DB_CONFIG)
            if self.connection.is_connected():
                print("Successfully connected to MySQL database")
                return True
        except Error as e:
            print(f"Error connecting to MySQL: {e}")
            return False
    
    def create_tables(self):
        """Create necessary tables if they don't exist"""
        try:
            cursor = self.connection.cursor()
            
            # Members table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS members (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    phone_number VARCHAR(20),
                    british_council_score VARCHAR(50),
                    student_field VARCHAR(100),
                    package_type VARCHAR(50),
                    registration_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT FALSE
                )
            """)
            
            # Payments table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    member_id INT,
                    telegram_id BIGINT NOT NULL,
                    payment_date DATE NOT NULL,
                    expiration_date DATE NOT NULL,
                    amount DECIMAL(10, 2),
                    currency VARCHAR(10),
                    invoice_image_path VARCHAR(500),
                    status ENUM('pending', 'verified', 'expired') DEFAULT 'pending',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
                )
            """)
            
            # Group assignments table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS group_assignments (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    member_id INT,
                    telegram_id BIGINT NOT NULL,
                    group_name VARCHAR(100),
                    group_id BIGINT,
                    group_db_id INT,
                    assigned_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
                    FOREIGN KEY (group_db_id) REFERENCES telegram_groups(id) ON DELETE CASCADE,
                    INDEX idx_telegram_id (telegram_id),
                    INDEX idx_group_id (group_id)
                )
            """)
            
            # Reminders table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    member_id INT,
                    telegram_id BIGINT NOT NULL,
                    reminder_date DATE NOT NULL,
                    sent BOOLEAN DEFAULT FALSE,
                    sent_at DATETIME,
                    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
                )
            """)
            
            # Payment tracking table for income reports
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS payment_tracking (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    member_id INT,
                    student_name VARCHAR(255),
                    telegram_id BIGINT,
                    package_type VARCHAR(50),
                    amount DECIMAL(10, 2),
                    payment_date DATE NOT NULL,
                    month_year VARCHAR(7),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
                    INDEX idx_month_year (month_year),
                    INDEX idx_package_type (package_type),
                    INDEX idx_telegram_id (telegram_id)
                )
            """)
            
            # Telegram groups table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS telegram_groups (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    group_type ENUM('general', 'class') NOT NULL,
                    group_name VARCHAR(255) NOT NULL,
                    group_id BIGINT UNIQUE NOT NULL,
                    level_category VARCHAR(1),
                    package_type VARCHAR(50),
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_group_type (group_type),
                    INDEX idx_level_package (level_category, package_type)
                )
            """)
            
            # Class schedule table for Google Meet
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS class_schedule (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    package_type VARCHAR(50) NOT NULL,
                    level_category VARCHAR(1) NOT NULL,
                    day_of_week VARCHAR(10) NOT NULL,
                    time VARCHAR(5) NOT NULL,
                    duration_minutes INT DEFAULT 90,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_active (is_active),
                    INDEX idx_package_level (package_type, level_category)
                )
            """)
            
            # Meet links table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS meet_links (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    schedule_id INT NOT NULL,
                    meet_link VARCHAR(500) NOT NULL,
                    event_id VARCHAR(255),
                    scheduled_time DATETIME NOT NULL,
                    sent BOOLEAN DEFAULT FALSE,
                    sent_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (schedule_id) REFERENCES class_schedule(id) ON DELETE CASCADE,
                    INDEX idx_scheduled_time (scheduled_time),
                    INDEX idx_sent (sent)
                )
            """)
            
            self.connection.commit()
            print("Database tables created successfully")
            return True
            
        except Error as e:
            print(f"Error creating tables: {e}")
            return False
    
    def add_member(self, telegram_id, username, first_name, last_name):
        """Add a new member to the database"""
        try:
            cursor = self.connection.cursor()
            query = """
                INSERT INTO members (telegram_id, username, first_name, last_name)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    username = VALUES(username),
                    first_name = VALUES(first_name),
                    last_name = VALUES(last_name)
            """
            cursor.execute(query, (telegram_id, username, first_name, last_name))
            self.connection.commit()
            return cursor.lastrowid
        except Error as e:
            print(f"Error adding member: {e}")
            return None
    
    def update_british_council_score(self, telegram_id, british_council_score):
        """Update member's British Council score"""
        try:
            cursor = self.connection.cursor()
            query = """
                UPDATE members 
                SET british_council_score = %s
                WHERE telegram_id = %s
            """
            cursor.execute(query, (british_council_score, telegram_id))
            self.connection.commit()
            return True
        except Error as e:
            print(f"Error updating British Council score: {e}")
            return False
    
    def update_phone_number(self, telegram_id, phone_number):
        """Update member's phone number"""
        try:
            cursor = self.connection.cursor()
            query = """
                UPDATE members 
                SET phone_number = %s
                WHERE telegram_id = %s
            """
            cursor.execute(query, (phone_number, telegram_id))
            self.connection.commit()
            return True
        except Error as e:
            print(f"Error updating phone number: {e}")
            return False
    
    def update_member_field(self, telegram_id, student_field):
        """Update member's student field"""
        try:
            cursor = self.connection.cursor()
            query = """
                UPDATE members 
                SET student_field = %s
                WHERE telegram_id = %s
            """
            cursor.execute(query, (student_field, telegram_id))
            self.connection.commit()
            return True
        except Error as e:
            print(f"Error updating member field: {e}")
            return False
    
    def update_member_package(self, telegram_id, package_type):
        """Update member's package type"""
        try:
            cursor = self.connection.cursor()
            query = """
                UPDATE members 
                SET package_type = %s
                WHERE telegram_id = %s
            """
            cursor.execute(query, (package_type, telegram_id))
            self.connection.commit()
            return True
        except Error as e:
            print(f"Error updating member package: {e}")
            return False
    
    def add_payment(self, telegram_id, payment_date, amount=None, currency=None, invoice_path=None):
        """Add a payment record and calculate expiration date"""
        try:
            cursor = self.connection.cursor()
            
            # Get member_id
            cursor.execute("SELECT id FROM members WHERE telegram_id = %s", (telegram_id,))
            result = cursor.fetchone()
            if not result:
                return None
            
            member_id = result[0]
            
            # Calculate expiration date
            expiration_date = payment_date + timedelta(days=config.SUBSCRIPTION_DAYS)
            
            query = """
                INSERT INTO payments 
                (member_id, telegram_id, payment_date, expiration_date, amount, currency, invoice_image_path, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'verified')
            """
            cursor.execute(query, (member_id, telegram_id, payment_date, expiration_date, 
                                 amount, currency, invoice_path))
            self.connection.commit()
            
            # Schedule reminder
            reminder_date = expiration_date - timedelta(days=config.REMINDER_DAYS_BEFORE)
            self.schedule_reminder(member_id, telegram_id, reminder_date)
            
            return expiration_date
        except Error as e:
            print(f"Error adding payment: {e}")
            return None
    
    def schedule_reminder(self, member_id, telegram_id, reminder_date):
        """Schedule a payment reminder"""
        try:
            cursor = self.connection.cursor()
            query = """
                INSERT INTO reminders (member_id, telegram_id, reminder_date)
                VALUES (%s, %s, %s)
            """
            cursor.execute(query, (member_id, telegram_id, reminder_date))
            self.connection.commit()
            return True
        except Error as e:
            print(f"Error scheduling reminder: {e}")
            return False
    
    def get_member_status(self, telegram_id):
        """Check if member has active subscription"""
        try:
            cursor = self.connection.cursor(dictionary=True)
            query = """
                SELECT p.*, m.british_council_score 
                FROM payments p
                JOIN members m ON p.member_id = m.id
                WHERE p.telegram_id = %s 
                AND p.status = 'verified'
                AND p.expiration_date >= CURDATE()
                ORDER BY p.expiration_date DESC
                LIMIT 1
            """
            cursor.execute(query, (telegram_id,))
            return cursor.fetchone()
        except Error as e:
            print(f"Error checking member status: {e}")
            return None
    
    def get_expired_members(self):
        """Get list of members whose subscription has expired"""
        try:
            cursor = self.connection.cursor(dictionary=True)
            query = """
                SELECT DISTINCT m.telegram_id, m.username, m.first_name, p.expiration_date
                FROM members m
                JOIN payments p ON m.id = p.member_id
                WHERE p.expiration_date < CURDATE()
                AND p.status = 'verified'
                AND m.is_active = TRUE
            """
            cursor.execute(query)
            return cursor.fetchall()
        except Error as e:
            print(f"Error getting expired members: {e}")
            return []
    
    def get_pending_reminders(self):
        """Get reminders that need to be sent"""
        try:
            cursor = self.connection.cursor(dictionary=True)
            query = """
                SELECT r.*, m.username, m.first_name
                FROM reminders r
                JOIN members m ON r.member_id = m.id
                WHERE r.reminder_date <= CURDATE()
                AND r.sent = FALSE
            """
            cursor.execute(query)
            return cursor.fetchall()
        except Error as e:
            print(f"Error getting pending reminders: {e}")
            return []
    
    def mark_reminder_sent(self, reminder_id):
        """Mark a reminder as sent"""
        try:
            cursor = self.connection.cursor()
            query = """
                UPDATE reminders 
                SET sent = TRUE, sent_at = NOW()
                WHERE id = %s
            """
            cursor.execute(query, (reminder_id,))
            self.connection.commit()
            return True
        except Error as e:
            print(f"Error marking reminder sent: {e}")
            return False
    
    def add_group_assignment(self, telegram_id, group_name, group_id):
        """Record group assignment for a member"""
        try:
            cursor = self.connection.cursor()
            
            # Get member_id
            cursor.execute("SELECT id FROM members WHERE telegram_id = %s", (telegram_id,))
            result = cursor.fetchone()
            if not result:
                return False
            
            member_id = result[0]
            
            query = """
                INSERT INTO group_assignments (member_id, telegram_id, group_name, group_id)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(query, (member_id, telegram_id, group_name, group_id))
            self.connection.commit()
            return True
        except Error as e:
            print(f"Error adding group assignment: {e}")
            return False
    
    def record_payment_tracking(self, member_id, package_type, amount, payment_date):
        """Record payment for income tracking with student details"""
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            # Get student name and telegram_id from members table
            cursor.execute("""
                SELECT telegram_id, CONCAT(COALESCE(first_name, ''), ' ', COALESCE(last_name, '')) as student_name
                FROM members 
                WHERE id = %s
            """, (member_id,))
            member = cursor.fetchone()
            
            if not member:
                return False
            
            telegram_id = member['telegram_id']
            student_name = member['student_name'].strip()
            
            # Calculate month_year (e.g., "2025-11" for November 2025)
            month_year = payment_date.strftime('%Y-%m')
            
            query = """
                INSERT INTO payment_tracking (member_id, student_name, telegram_id, package_type, amount, payment_date, month_year)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (member_id, student_name, telegram_id, package_type, amount, payment_date, month_year))
            self.connection.commit()
            return True
        except Error as e:
            print(f"Error recording payment tracking: {e}")
            return False
    
    def get_monthly_income_report(self, month_year=None):
        """Get income report for a specific month or current month"""
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            if not month_year:
                # Get current month
                from datetime import datetime
                month_year = datetime.now().strftime('%Y-%m')
            
            # Total income by package type
            query = """
                SELECT 
                    package_type,
                    COUNT(*) as payment_count,
                    SUM(amount) as total_amount
                FROM payment_tracking
                WHERE month_year = %s
                GROUP BY package_type
            """
            cursor.execute(query, (month_year,))
            results = cursor.fetchall()
            
            # Calculate overall total
            total_income = sum(r['total_amount'] for r in results if r['total_amount'])
            
            return {
                'month_year': month_year,
                'by_package': results,
                'total_income': total_income
            }
        except Error as e:
            print(f"Error getting income report: {e}")
            return None
    
    def close(self):
        """Close database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("Database connection closed")