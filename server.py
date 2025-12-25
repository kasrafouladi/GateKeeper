import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import json
import os

# Logging settings
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Storage files
DATA_FILE = 'bot_data.json'

class RoomBot:
    def __init__(self):
        self.owner_id = None  # Should be set via /setowner command
        self.rooms = {}  # {room_name: {'admins': [user_ids], 'chat_id': chat_id}}
        self.user_messages = {}  # {message_id: {'user_id': x, 'room': y, 'text': z}}
        self.load_data()
    
    def load_data(self):
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.owner_id = data.get('owner_id')
                self.rooms = data.get('rooms', {})
                self.user_messages = data.get('user_messages', {})
    
    def save_data(self):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'owner_id': self.owner_id,
                'rooms': self.rooms,
                'user_messages': self.user_messages
            }, f, ensure_ascii=False, indent=2)

bot_manager = RoomBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if bot_manager.owner_id is None:
        await update.message.reply_text(
            "⚠️ Owner not set yet. Use /setowner command."
        )
        return
    
    if user_id == bot_manager.owner_id:
        keyboard = [
            [InlineKeyboardButton("➕ Create Room", callback_data='create_room')],
            [InlineKeyboardButton("🗑 Delete Room", callback_data='delete_room')],
            [InlineKeyboardButton("👤 Manage Admins", callback_data='manage_admins')],
            [InlineKeyboardButton("📋 Room List", callback_data='list_rooms')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("👑 Hello Owner! What can I do for you?", reply_markup=reply_markup)
    else:
        if bot_manager.rooms:
            keyboard = [[InlineKeyboardButton(room, callback_data=f'select_room:{room}')] 
                       for room in bot_manager.rooms.keys()]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Hello! Select a room to send a message:", reply_markup=reply_markup)
        else:
            await update.message.reply_text("No rooms created yet.")

async def setowner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if bot_manager.owner_id is None:
        bot_manager.owner_id = update.effective_user.id
        bot_manager.save_data()
        await update.message.reply_text(f"✅ You have been set as owner! (ID: {bot_manager.owner_id})")
    else:
        await update.message.reply_text(f"⚠️ Owner already set. (ID: {bot_manager.owner_id})")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    
    if data == 'create_room':
        await query.edit_message_text("📝 Send the name of the new room:")
        context.user_data['action'] = 'create_room'
    
    elif data == 'delete_room':
        if not bot_manager.rooms:
            await query.edit_message_text("❌ No rooms exist.")
            return
        keyboard = [[InlineKeyboardButton(room, callback_data=f'del_room:{room}')] 
                   for room in bot_manager.rooms.keys()]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Select a room to delete:", reply_markup=reply_markup)
    
    elif data.startswith('del_room:'):
        room_name = data.split(':', 1)[1]
        if room_name in bot_manager.rooms:
            del bot_manager.rooms[room_name]
            bot_manager.save_data()
            await query.edit_message_text(f"✅ Room '{room_name}' deleted.")
        else:
            await query.edit_message_text("❌ Room not found.")
    
    elif data == 'manage_admins':
        if not bot_manager.rooms:
            await query.edit_message_text("❌ No rooms exist.")
            return
        keyboard = [[InlineKeyboardButton(room, callback_data=f'admin_room:{room}')] 
                   for room in bot_manager.rooms.keys()]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Select a room to manage admins:", reply_markup=reply_markup)
    
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
    
    elif data.startswith('add_admin:'):
        room_name = data.split(':', 1)[1]
        context.user_data['action'] = 'add_admin'
        context.user_data['admin_room'] = room_name
        await query.edit_message_text(f"📝 Send user ID to add to '{room_name}':")
    
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
    
    elif data == 'list_rooms':
        if not bot_manager.rooms:
            await query.edit_message_text("❌ No rooms exist.")
            return
        room_list = "\n\n".join([
            f"🏠 {room}\n👥 Admins: {', '.join(map(str, info.get('admins', []))) or 'None'}"
            for room, info in bot_manager.rooms.items()
        ])
        await query.edit_message_text(f"📋 Room List:\n\n{room_list}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    # If user is in the middle of an action
    action = context.user_data.get('action')
    
    if user_id == bot_manager.owner_id:
        if action == 'create_room':
            room_name = text.strip()
            bot_manager.rooms[room_name] = {'admins': []}
            bot_manager.save_data()
            context.user_data.pop('action', None)
            await update.message.reply_text(f"✅ Room '{room_name}' created!")
            return
        
        elif action == 'add_admin':
            try:
                admin_id = int(text.strip())
                room_name = context.user_data.get('admin_room')
                if 'admins' not in bot_manager.rooms[room_name]:
                    bot_manager.rooms[room_name]['admins'] = []
                if admin_id not in bot_manager.rooms[room_name]['admins']:
                    bot_manager.rooms[room_name]['admins'].append(admin_id)
                    bot_manager.save_data()
                    await update.message.reply_text(f"✅ Admin {admin_id} added to '{room_name}'!")
                else:
                    await update.message.reply_text("⚠️ This user is already an admin.")
                context.user_data.pop('action', None)
            except ValueError:
                await update.message.reply_text("❌ Please send a valid number.")
            return
    
    # Regular user sending message to room
    selected_room = context.user_data.get('selected_room')
    if not selected_room:
        await update.message.reply_text("Please first select a room with /start.")
        return
    
    if selected_room not in bot_manager.rooms:
        await update.message.reply_text("❌ The selected room doesn't exist.")
        return
    
    # Send message to all room admins
    admins = bot_manager.rooms[selected_room].get('admins', [])
    if not admins:
        await update.message.reply_text("⚠️ This room has no admins.")
        return
    
    # Save user message
    message_id = str(update.message.message_id) + str(user_id)
    bot_manager.user_messages[message_id] = {
        'user_id': user_id,
        'room': selected_room,
        'text': text,
        'message_id': update.message.message_id
    }
    bot_manager.save_data()
    
    # Send to admins
    for admin_id in admins:
        try:
            keyboard = [[InlineKeyboardButton("💬 Reply", callback_data=f'reply:{message_id}')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"📨 New message from user {user_id}\n🏠 Room: {selected_room}\n\n{text}",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error sending to admin {admin_id}: {e}")
    
    # Send to owner
    try:
        keyboard = [[InlineKeyboardButton("💬 Reply", callback_data=f'reply:{message_id}')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=bot_manager.owner_id,
            text=f"📨 New message from user {user_id}\n🏠 Room: {selected_room}\n\n{text}",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error sending to owner: {e}")
    
    await update.message.reply_text("✅ Your message has been sent!")

async def reply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('reply:'):
        message_id = query.data.split(':', 1)[1]
        context.user_data['reply_to'] = message_id
        await query.edit_message_text(
            f"{query.message.text}\n\n💬 Send your reply:"
        )

async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    reply_to = context.user_data.get('reply_to')
    
    if not reply_to:
        await handle_message(update, context)
        return
    
    # Check permission
    is_admin = False
    for room_info in bot_manager.rooms.values():
        if user_id in room_info.get('admins', []) or user_id == bot_manager.owner_id:
            is_admin = True
            break
    
    if not is_admin:
        await update.message.reply_text("⛔️ You don't have permission.")
        return
    
    # Get original message info
    original_msg = bot_manager.user_messages.get(reply_to)
    if not original_msg:
        await update.message.reply_text("❌ Original message not found.")
        return
    
    # Send reply to user
    try:
        await context.bot.send_message(
            chat_id=original_msg['user_id'],
            text=f"💬 Reply from admin of room '{original_msg['room']}':\n\n{update.message.text}\n\n"
                 f"🔄 In reply to: {original_msg['text'][:50]}..."
        )
        await update.message.reply_text("✅ Your reply has been sent!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error sending: {e}")
    
    context.user_data.pop('reply_to', None)

def main():
    TOKEN = "YOUR_BOT_TOKEN_HERE"  # Put your bot token here
    
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setowner", setowner))
    application.add_handler(CallbackQueryHandler(button_callback, pattern='^(?!reply:).*'))
    application.add_handler(CallbackQueryHandler(reply_callback, pattern='^reply:'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reply))
    
    logger.info("🤖 Bot started...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
