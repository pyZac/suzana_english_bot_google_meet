from telegram.error import TelegramError

class GroupManager:
    def __init__(self, db_handler, bot):
        self.db = db_handler
        self.bot = bot
        self.level_groups = {'A': ['A1', 'A2'], 'B': ['B1', 'B2'], 'C': ['C1', 'C2']}
        self.MIN_STUDENTS = 2
        self.MAX_STUDENTS = 4
        
        # Admin IDs to exclude from student count
        self.admin_ids = [6233703198, 926422038]  # Developer and Suzana
        self.bot_id = None  # Will be set when bot starts
    
    def set_bot_id(self, bot_id):
        """Set the bot's own ID"""
        self.bot_id = bot_id
    
    def get_level_category(self, british_council_score):
        for category, levels in self.level_groups.items():
            if british_council_score in levels:
                return category
        return None
    
    def register_group(self, group_id, group_type, group_name, level_category=None, package_type=None):
        cursor = self.db.connection.cursor()
        try:
            cursor.execute("""INSERT INTO telegram_groups (group_type, group_name, group_id, level_category, package_type, is_active)
                VALUES (%s, %s, %s, %s, %s, TRUE) ON DUPLICATE KEY UPDATE group_name = VALUES(group_name),
                level_category = VALUES(level_category), package_type = VALUES(package_type)""",
                (group_type, group_name, group_id, level_category, package_type))
            self.db.connection.commit()
            return True
        except Exception as e:
            print(f"Error: {e}")
            return False
    
    def get_general_group(self):
        cursor = self.db.connection.cursor(dictionary=True)
        cursor.execute("SELECT group_id FROM telegram_groups WHERE group_type = 'general' AND is_active = TRUE LIMIT 1")
        result = cursor.fetchone()
        return result['group_id'] if result else None
    
    async def get_actual_student_count(self, group_id):
        """Get the actual number of students in a group (excluding admins and bot)"""
        try:
            # Get member count from Telegram
            member_count = await self.bot.get_chat_member_count(chat_id=group_id)
            
            # Exclude admins (you + Suzana) and bot
            excluded_count = len(self.admin_ids)
            if self.bot_id:
                excluded_count += 1
            
            # Calculate actual student count
            student_count = member_count - excluded_count
            
            # Make sure it's not negative
            return max(0, student_count)
        except TelegramError as e:
            print(f"Error getting member count for group {group_id}: {e}")
            return 0
    
    async def find_available_class(self, level_category, package_type):
        cursor = self.db.connection.cursor(dictionary=True)
        
        # Get all class groups for this level and package
        cursor.execute("""SELECT g.* FROM telegram_groups g
            WHERE g.group_type = 'class'
            AND g.level_category = %s AND g.package_type = %s AND g.is_active = TRUE
            ORDER BY g.id ASC""",
            (level_category, package_type))
        
        groups = cursor.fetchall()
        
        # Check each group to find one with space
        for group in groups:
            student_count = await self.get_actual_student_count(group['group_id'])
            print(f"Group {group['group_name']} has {student_count} students (max: {self.MAX_STUDENTS})")
            
            if student_count < self.MAX_STUDENTS:
                group['student_count'] = student_count
                return group
        
        # No available group found
        return None
    
    async def assign_student_to_groups(self, telegram_id, british_council_score, package_type):
        results = {'general_group': None, 'class_group': None, 'waiting_list': False, 'invite_links': []}
        cursor = self.db.connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM members WHERE telegram_id = %s", (telegram_id,))
        member = cursor.fetchone()
        if not member:
            return results
        
        # Get bot's own ID if not set
        if not self.bot_id:
            bot_info = await self.bot.get_me()
            self.set_bot_id(bot_info.id)
        
        general_group_id = self.get_general_group()
        if general_group_id:
            try:
                invite = await self.bot.create_chat_invite_link(chat_id=general_group_id, member_limit=1)
                results['general_group'] = general_group_id
                results['invite_links'].append({'name': 'Suzana English Community', 'link': invite.invite_link})
                self.db.add_group_assignment(telegram_id, "Suzana English Community", general_group_id)
            except TelegramError as e:
                print(f"Error creating invite for general group: {e}")
        
        level_category = self.get_level_category(british_council_score)
        if level_category:
            available_class = await self.find_available_class(level_category, package_type)
            if available_class:
                try:
                    invite = await self.bot.create_chat_invite_link(chat_id=available_class['group_id'], member_limit=1)
                    results['class_group'] = available_class
                    results['invite_links'].append({'name': available_class['group_name'], 'link': invite.invite_link})
                    cursor.execute("SELECT id FROM telegram_groups WHERE group_id = %s", (available_class['group_id'],))
                    group_db = cursor.fetchone()
                    cursor.execute("""INSERT INTO group_assignments (member_id, telegram_id, group_name, group_id, group_db_id)
                        VALUES (%s, %s, %s, %s, %s)""", 
                        (member['id'], telegram_id, available_class['group_name'], available_class['group_id'], group_db['id']))
                    self.db.connection.commit()
                except TelegramError as e:
                    print(f"Error creating invite for class group: {e}")
                    results['waiting_list'] = True
            else:
                print(f"No available class found for level {level_category} and package {package_type}")
                results['waiting_list'] = True
        return results