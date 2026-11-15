import base64
import json
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
import config

class InvoiceHandler:
    def __init__(self, db_handler, group_manager=None):
        self.db = db_handler
        self.group_manager = group_manager
        # Get expected receiver from config
        self.expected_receiver = config.EXPECTED_RECEIVER
    
    async def process_invoice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process invoice image sent by user"""
        user = update.effective_user
        
        # Check if user is registered
        cursor = self.db.connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM members WHERE telegram_id = %s", (user.id,))
        member = cursor.fetchone()
        
        if not member:
            await update.message.reply_text(
                "⚠️ You need to register first!\n\nPlease use /start to register."
            )
            return
        
        # Get the photo
        if update.message.photo:
            # Get the largest photo
            photo = update.message.photo[-1]
            
            # Download the photo
            photo_file = await photo.get_file()
            photo_bytes = await photo_file.download_as_bytearray()
            
            # Send processing message
            processing_msg = await update.message.reply_text(
                "🔍 Processing your invoice...\nPlease wait..."
            )
            
            try:
                # Extract invoice data using Tesseract OCR
                invoice_data = await self.extract_invoice_data(photo_bytes)
                
                if invoice_data.get('error'):
                    await processing_msg.edit_text(
                        f"❌ Error reading invoice: {invoice_data['error']}\n\n"
                        "Please make sure the image is clear and try again."
                    )
                    return
                
                # Verify receiver name
                # Normalize both strings to remove Arabic diacritics and special characters
                def normalize_text(text):
                    import unicodedata
                    # Remove diacritics and formatting characters
                    text = ''.join(c for c in unicodedata.normalize('NFKD', text) 
                                  if not unicodedata.combining(c))
                    # Remove common Arabic/RTL markers
                    text = text.replace('\u200f', '').replace('\u200e', '').replace('\u202a', '').replace('\u202b', '').replace('\u202c', '')
                    return text.strip().lower()
                
                normalized_receiver = normalize_text(invoice_data['receiver'])
                normalized_expected = normalize_text(self.expected_receiver)
                
                if normalized_receiver != normalized_expected:
                    await processing_msg.edit_text(
                        f"❌ **Payment Verification Failed**\n\n"
                        f"The payment was sent to: **{invoice_data['receiver']}**\n"
                        f"Expected receiver: **{self.expected_receiver}**\n\n"
                        f"Please make sure you sent the payment to the correct account."
                    )
                    return
                
                # Parse the date
                try:
                    payment_date = datetime.strptime(invoice_data['date'], '%d-%m-%Y').date()
                except:
                    await processing_msg.edit_text(
                        "❌ Could not read the payment date from the invoice.\n\n"
                        "Please make sure the date is clearly visible and try again."
                    )
                    return
                
                # Save invoice image to tmp directory
                invoice_dir = "/tmp/suzana_invoices"
                invoice_path = f"{invoice_dir}/{user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                import os
                os.makedirs(invoice_dir, exist_ok=True)
                with open(invoice_path, 'wb') as f:
                    f.write(photo_bytes)
                
                # Add payment to database
                expiration_date = self.db.add_payment(
                    telegram_id=user.id,
                    payment_date=payment_date,
                    amount=invoice_data['amount'],
                    currency='SYP',
                    invoice_path=invoice_path
                )
                
                if expiration_date:
                    # Activate the member
                    cursor.execute(
                        "UPDATE members SET is_active = TRUE WHERE telegram_id = %s",
                        (user.id,)
                    )
                    self.db.connection.commit()
                    
                    # Get member package info
                    package_type = member.get('package_type', 'Unknown')
                    british_council_score = member.get('british_council_score', 'A1')
                    
                    # For display purposes, add "Package" if it's not already there
                    display_package = package_type if "Package" in package_type else f"{package_type} Package"
                    
                    # Record in payment tracking table
                    self.db.record_payment_tracking(
                        member_id=member['id'],
                        package_type=package_type,
                        amount=invoice_data['amount'],
                        payment_date=payment_date
                    )
                    
                    # Assign to groups
                    group_results = None
                    if self.group_manager:
                        group_results = await self.group_manager.assign_student_to_groups(
                            telegram_id=user.id,
                            british_council_score=british_council_score,
                            package_type=package_type
                        )
                    
                    # Build success message
                    success_message = (
                        f"✅ **Payment Verified Successfully!**\n\n"
                        f"📋 **Invoice Details:**\n"
                        f"• **From:** {invoice_data['sender']}\n"
                        f"• **To:** {invoice_data['receiver']}\n"
                        f"• **Amount:** {invoice_data['amount']:,.0f} SYP\n"
                        f"• **Date:** {invoice_data['date']}\n\n"
                        f"🎉 **Your subscription is now active!**\n"
                        f"📅 **Valid until:** {expiration_date.strftime('%d-%m-%Y')}\n"
                        f"📦 **Package:** {display_package}\n"
                        f"📚 **Level:** {british_council_score}\n\n"
                    )
                    
                    # Add group assignment info with invite links
                    if group_results:
                        if group_results.get('invite_links'):
                            success_message += "🔗 **Join Your Groups:**\n"
                            for group_info in group_results['invite_links']:
                                success_message += f"• [{group_info['name']}]({group_info['link']})\n"
                            success_message += "\n👆 Click the links above to join!\n"
                        elif group_results.get('waiting_list'):
                            success_message += "\n⏳ You're on the waiting list for a class.\n"
                            success_message += "We need at least 2 students to start a class.\n"
                            success_message += "You'll be notified when your class is ready!\n"
                    
                    success_message += f"\n💡 You'll receive a reminder 3 days before expiration."
                    
                    # Send success message
                    await processing_msg.edit_text(
                        success_message,
                        parse_mode='Markdown'
                    )
                else:
                    await processing_msg.edit_text(
                        "❌ Error processing payment. Please contact support."
                    )
                    
            except Exception as e:
                print(f"Error processing invoice: {e}")
                await processing_msg.edit_text(
                    "❌ An error occurred while processing your invoice.\n\n"
                    "Please try again or contact support."
                )
        else:
            await update.message.reply_text(
                "📸 Please send a photo of your Sham Cash invoice."
            )
    
    async def extract_invoice_data(self, image_bytes):
        """Extract data from invoice using Tesseract OCR"""
        import pytesseract
        from PIL import Image
        import io
        import re
        
        try:
            # Open image from bytes
            image = Image.open(io.BytesIO(image_bytes))
            
            # Use Tesseract to extract Arabic text
            custom_config = r'--oem 3 --psm 6 -l ara+eng'
            text = pytesseract.image_to_string(image, config=custom_config)
            
            print(f"Extracted text: {text}")
            
            # Extract information using regex patterns
            invoice_data = {}
            
            # Extract sender
            sender_match = re.search(r'(?:اسم المرسل|المرسل)[:\s]*([^\n]+)', text)
            if sender_match:
                invoice_data['sender'] = sender_match.group(1).strip()
            else:
                sender_match = re.search(r'salem\s*\d+', text, re.IGNORECASE)
                if sender_match:
                    invoice_data['sender'] = sender_match.group(0).strip()
                else:
                    return {'error': 'Could not find sender name'}
            
            # Extract receiver
            receiver_match = re.search(r'(?:اسم المستلم|المستلم)[:\s]*([^\n]+)', text)
            if receiver_match:
                invoice_data['receiver'] = receiver_match.group(1).strip()
            else:
                receiver_match = re.search(r'firasraslan', text, re.IGNORECASE)
                if receiver_match:
                    invoice_data['receiver'] = receiver_match.group(0).strip()
                else:
                    return {'error': 'Could not find receiver name'}
            
            # Extract date - multiple format support
            date_patterns = [
                r'(\d{4})-(\d{2})-(\d{2})',
                r'(\d{2})-(\d{2})-(\d{4})',
                r'(\d{2})/(\d{2})/(\d{4})',
                r'(\d{4})/(\d{2})/(\d{2})',
                r'(\d{2})\.(\d{2})\.(\d{4})',
            ]
            
            date_found = False
            for pattern in date_patterns:
                date_match = re.search(pattern, text)
                if date_match:
                    parts = date_match.groups()
                    if len(parts[0]) == 4:
                        year, month, day = parts
                    else:
                        day, month, year = parts
                    invoice_data['date'] = f"{day}-{month}-{year}"
                    date_found = True
                    break
            
            if not date_found:
                print(f"DEBUG: Could not find date. Text: {text[:500]}")
                return {'error': 'Could not find payment date. Please make sure the date is clearly visible.'}
            
            # Extract amount
            amount_match = re.search(r'(?:s\.p|المبلغ)[:\s]*([0-9,\.]+)', text, re.IGNORECASE)
            if amount_match:
                amount_str = amount_match.group(1).replace(',', '').replace('.', '')
                invoice_data['amount'] = float(amount_str)
            else:
                amount_match = re.search(r'(\d{3,})[,\s]*\d{3}', text)
                if amount_match:
                    amount_str = amount_match.group(0).replace(',', '').replace(' ', '')
                    invoice_data['amount'] = float(amount_str)
                else:
                    return {'error': 'Could not find payment amount'}
            
            return invoice_data
            
        except Exception as e:
            print(f"Error in Tesseract OCR: {e}")
            return {'error': str(e)}