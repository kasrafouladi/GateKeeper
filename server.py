import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import json
import os

# Log settings
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Storage files
DATA_FILE = 'bot_data.json'

class RoomBot:
    def __init__(self):
        self.owner_id = None  # Set via /setowner command
        self.rooms = {}  # {room_name: {'admins': [user_ids], 'chat_id': chat_id}}
        self.user_messages = {}  # {message_id: {'user_id': x, 'room': y, 'chat_id': z}}
        self.load_data()
    
    def load_data(self):
        """Load bot data from JSON file"""
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.owner_id = data.get('owner_id')
                self.rooms = data.get('rooms', {})
                self.user_messages = data.get('user_messages', {})
    
    def save_data(self):
        """Save bot data to JSON file"""
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'owner_id': self.owner_id,
                'rooms': self.rooms,
                'user_messages': self.user_messages
            }, f, ensure_ascii=False, indent=2)

bot_manager = RoomBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user_id = update.effective_user.id
    
    # Check if owner is set
    if bot_manager.owner_id is None:
        await update.message.reply_text(
            "⚠️ Owner not set yet. Use the /setowner command."
        )
        return
    
    # Owner menu
    if user_id == bot_manager.owner_id:
        keyboard = [
            [InlineKeyboardButton("➕ Create Room", callback_data='create_room')],
            [InlineKeyboardButton("🗑 Delete Room", callback_data='delete_room')],
            [InlineKeyboardButton("👤 Manage Admins", callback_data='manage_admins')],
            [InlineKeyboardButton("📋 List Rooms", callback_data='list_rooms')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("👑 Hello Owner! What can I do for you?", reply_markup=reply_markup)
    else:
        # Regular user - show available rooms
        if bot_manager.rooms:
            keyboard = [[InlineKeyboardButton(room, callback_data=f'select_room:{room}')] 
                       for room in bot_manager.rooms.keys()]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Hello! Select a room to send a message:", reply_markup=reply_markup)
        else:
            await update.message.reply_text("No rooms have been created yet.")

async def setowner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set bot owner (can only be done once)"""
    if bot_manager.owner_id is None:
        bot_manager.owner_id = update.effective_user.id
        bot_manager.save_data()
        await update.message.reply_text(f"✅ You have been set as owner! (ID: {bot_manager.owner_id})")
    else:
        await update.message.reply_text(f"⚠️ Owner is already set. (ID: {bot_manager.owner_id})")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    # Room selection by regular user
    if data.startswith('select_room:'):
        room_name = data.split(':', 1)[1]
        context.user_data['selected_room'] = room_name
        await query.edit_message_text(f"✅ Room '{room_name}' selected. Now send your message.")
        return
    
    # Only owner can access the rest
    if user_id != bot_manager.owner_id:
        await query.edit_message_text("⛔️ You don't have permission.")
        return
    
    # Create room
    if data == 'create_room':
        await query.edit_message_text("📝 Send the name of the new room:")
        context.user_data['action'] = 'create_room'
    
    # Delete room
    elif data == 'delete_room':
        if not bot_manager.rooms:
            await query.edit_message_text("❌ No rooms exist.")
            return
        keyboard = [[InlineKeyboardButton(room, callback_data=f'del_room:{room}')] 
                   for room in bot_manager.rooms.keys()]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Select a room to delete:", reply_markup=reply_markup)
    
    # Confirm room deletion
    elif data.startswith('del_room:'):
        room_name = data.split(':', 1)[1]
        if room_name in bot_manager.rooms:
            del bot_manager.rooms[room_name]
            bot_manager.save_data()
            await query.edit_message_text(f"✅ Room '{room_name}' deleted.")
        else:
            await query.edit_message_text("❌ Room not found.")
    
    # Manage admins
    elif data == 'manage_admins':
        if not bot_manager.rooms:
            await query.edit_message_text("❌ No rooms exist.")
            return
        keyboard = [[InlineKeyboardButton(room, callback_data=f'admin_room:{room}')] 
                   for room in bot_manager.rooms.keys()]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Select a room to manage admins:", reply_markup=reply_markup)
    
    # Admin management for specific room
    elif data.startswith('admin_room:'):
        room_name = data.split(':', 1)[1]
        context.user_data['admin_room'] = room_name
        keyboard = [
            [InlineKeyboardButton("➕ Add Admin", callback_data=f'add_admin:{room_name}')],
            [InlineKeyboardButton("➖ Remove Admin", callback_data=f'remove_admin:{room_name}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        admins = bot_manager.rooms[room_name].get('admins', [])
        admin_list = '\n'.join([f"• {aid}" for aid in admins]) if admins else "No admins"
        await query.edit_message_text(
            f"🏠 Room: {room_name}\n👥 Admins:\n{admin_list}",
            reply_markup=reply_markup
        )
    
    # Add admin
    elif data.startswith('add_admin:'):
        room_name = data.split(':', 1)[1]
        context.user_data['action'] = 'add_admin'
        context.user_data['admin_room'] = room_name
        await query.edit_message_text(f"📝 Send user ID to add to '{room_name}':")
    
    # Remove admin
    elif data.startswith('remove_admin:'):
        room_name = data.split(':', 1)[1]
        admins = bot_manager.rooms[room_name].get('admins', [])
        if not admins:
            await query.edit_message_text("❌ This room has no admins.")
            return
        keyboard = [[InlineKeyboardButton(str(aid), callback_data=f'rmadmin:{room_name}:{aid}')] 
                   for aid in admins]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Select an admin to remove:", reply_markup=reply_markup)
    
    # Confirm admin removal
    elif data.startswith('rmadmin:'):
        parts = data.split(':', 2)
        room_name = parts[1]
        admin_id = int(parts[2])
        if admin_id in bot_manager.rooms[room_name]['admins']:
            bot_manager.rooms[room_name]['admins'].remove(admin_id)
            bot_manager.save_data()
            await query.edit_message_text(f"✅ Admin {admin_id} removed from '{room_name}'.")
        else:
            await query.edit_message_text("❌ Admin not found.")
    
    # List all rooms
    elif data == 'list_rooms':
        if not bot_manager.rooms:
            await query.edit_message_text("❌ No rooms exist.")
            return
        room_list = "\n\n".join([
            f"🏠 {room}\n👥 Admins: {', '.join(map(str, info.get('admins', []))) or 'None'}"
            for room, info in bot_manager.rooms.items()
        ])
        await query.edit_message_text(f"📋 Room List:\n\n{room_list}")

async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all non-command messages (text, photo, video, document, etc.)"""
    user_id = update.effective_user.id
    message = update.message
    
    # Check if user is performing an action (owner only)
    action = context.user_data.get('action')
    
    # Owner actions
    if user_id == bot_manager.owner_id:
        if action == 'create_room':
            if message.text:
                room_name = message.text.strip()
                bot_manager.rooms[room_name] = {'admins': []}
                bot_manager.save_data()
                context.user_data.pop('action', None)
                await message.reply_text(f"✅ Room '{room_name}' created!")
            else:
                await message.reply_text("❌ Please send a room name as text.")
            return
        
        elif action == 'add_admin':
            if message.text:
                try:
                    admin_id = int(message.text.strip())
                    room_name = context.user_data.get('admin_room')
                    if 'admins' not in bot_manager.rooms[room_name]:
                        bot_manager.rooms[room_name]['admins'] = []
                    if admin_id not in bot_manager.rooms[room_name]['admins']:
                        bot_manager.rooms[room_name]['admins'].append(admin_id)
                        bot_manager.save_data()
                        await message.reply_text(f"✅ Admin {admin_id} added to '{room_name}'!")
                    else:
                        await message.reply_text("⚠️ This user is already an admin.")
                    context.user_data.pop('action', None)
                    context.user_data.pop('admin_room', None)
                except ValueError:
                    await message.reply_text("❌ Please send a valid number.")
            else:
                await message.reply_text("❌ Please send a user ID as text.")
            return
    
    # Check if user is replying to a message (admin/owner reply)
    reply_to = context.user_data.get('reply_to')
    if reply_to:
        await handle_admin_reply(update, context)
        return
    
    # Check if regular user is sending a message to a room
    selected_room = context.user_data.get('selected_room')
    if selected_room:
        await handle_user_message(update, context, selected_room)
        return
    
    # If none of the above, guide the user
    await message.reply_text("Please first select a room with /start or start a conversation.")

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE, room_name: str):
    """Handle user messages to a room (forward to admins and owner)"""
    user_id = update.effective_user.id
    message = update.message
    
    # Check if room exists
    if room_name not in bot_manager.rooms:
        await message.reply_text("❌ The selected room does not exist.")
        context.user_data.pop('selected_room', None)
        return
    
    # Get room admins
    admins = bot_manager.rooms[room_name].get('admins', [])
    if not admins:
        await message.reply_text("⚠️ This room has no admins.")
        return
    
    # Generate unique message ID for tracking
    unique_msg_id = f"{message.message_id}_{user_id}_{room_name}"
    bot_manager.user_messages[unique_msg_id] = {
        'user_id': user_id,
        'room': room_name,
        'chat_id': message.chat_id,
        'message_id': message.message_id
    }
    bot_manager.save_data()
    
    # Send to all admins
    for admin_id in admins:
        try:
            # Send notification
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"📨 New message from user {user_id}\n🏠 Room: {room_name}"
            )
            
            # Forward the complete message (with all content)
            await message.forward(chat_id=admin_id)
            
            # Add reply button
            keyboard = [[InlineKeyboardButton("💬 Reply", callback_data=f'reply:{unique_msg_id}')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=admin_id,
                text="⬆️ Click the button below to reply:",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error sending to admin {admin_id}: {e}")
    
    # Send to owner
    try:
        if bot_manager.owner_id and bot_manager.owner_id not in admins:  # Don't duplicate if owner is also admin
            # Send notification
            await context.bot.send_message(
                chat_id=bot_manager.owner_id,
                text=f"📨 New message from user {user_id}\n🏠 Room: {room_name}"
            )
            
            # Forward the complete message
            await message.forward(chat_id=bot_manager.owner_id)
            
            # Add reply button
            keyboard = [[InlineKeyboardButton("💬 Reply", callback_data=f'reply:{unique_msg_id}')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=bot_manager.owner_id,
                text="⬆️ Click the button below to reply:",
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Error sending to owner: {e}")
    
    await message.reply_text("✅ Your message has been sent to the room admins!")

async def reply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle reply button callback"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('reply:'):
        message_id = query.data.split(':', 1)[1]
        context.user_data['reply_to'] = message_id
        
        # Get original message info
        original_msg = bot_manager.user_messages.get(message_id)
        if original_msg:
            await query.edit_message_text(
                f"💬 Replying to message from user {original_msg['user_id']}\n"
                f"🏠 Room: {original_msg['room']}\n\n"
                f"Send your reply:"
            )
        else:
            await query.edit_message_text("❌ Original message not found.")

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin replies to user messages"""
    user_id = update.effective_user.id
    message = update.message
    reply_to_id = context.user_data.get('reply_to')
    
    # Check permission (admin or owner)
    is_admin = False
    for room_info in bot_manager.rooms.values():
        if user_id in room_info.get('admins', []) or user_id == bot_manager.owner_id:
            is_admin = True
            break
    
    if not is_admin:
        await message.reply_text("⛔️ You don't have permission to reply.")
        context.user_data.pop('reply_to', None)
        return
    
    # Get original message info
    original_msg = bot_manager.user_messages.get(reply_to_id)
    if not original_msg:
        await message.reply_text("❌ Original message not found.")
        context.user_data.pop('reply_to', None)
        return
    
    # Send reply to user
    try:
        # First send a notification
        await context.bot.send_message(
            chat_id=original_msg['user_id'],
            text=f"💬 Reply from admin of room '{original_msg['room']}':"
        )
        
        # Forward or copy the admin's message to the user
        await message.forward(chat_id=original_msg['user_id'])
        
        await message.reply_text("✅ Your reply has been sent to the user!")
    except Exception as e:
        logger.error(f"Error sending reply: {e}")
        await message.reply_text(f"❌ Error sending reply: {e}")
    
    # Clear reply context
    context.user_data.pop('reply_to', None)

def main():
    """Main function to start the bot"""
    # Replace with your bot token
    TOKEN = "YOUR_BOT_TOKEN_HERE"
    
    # Create application
    application = Application.builder().token(TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setowner", setowner))
    application.add_handler(CallbackQueryHandler(button_callback, pattern='^(?!reply:).*'))
    application.add_handler(CallbackQueryHandler(reply_callback, pattern='^reply:'))
    
    # Handle all non-command messages (text, photo, video, document, etc.)
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_all_messages))
    
    # Start bot
    logger.info("🤖 Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
