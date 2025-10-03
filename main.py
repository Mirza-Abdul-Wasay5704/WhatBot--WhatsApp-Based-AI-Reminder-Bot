from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse
import httpx
import logging
import google.generativeai as genai
from googleapiclient.discovery import build
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleRequest
import datetime
import json
import os
import re
import pickle
import pytz
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# ---------------- CONFIG ----------------
# Configure clean logging format
import time
start_time = time.time()

# Get log level from environment
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
log_level_mapping = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR
}

logging.basicConfig(
    level=log_level_mapping.get(log_level, logging.INFO),
    format='%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s',
    datefmt='%H:%M:%S'
)

# Create logger for this module
logger = logging.getLogger("WhatBot")

# Suppress noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("googleapiclient").setLevel(logging.WARNING)
logging.getLogger("google.auth").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

logger.info("🤖 WhatBot Starting Up...")
logger.info("📱 WhatsApp Integration: Enabled")
logger.info("🧠 Gemini AI: Enabled")
logger.info("📅 Google Calendar: Checking...")

# Load configuration from environment variables
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
if not ACCESS_TOKEN:
    logger.error("❌ ACCESS_TOKEN not found in environment variables!")
    raise ValueError("ACCESS_TOKEN is required. Please check your .env file.")

WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "748333268371100")
WHATSAPP_URL = f"https://graph.facebook.com/v22.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
if not VERIFY_TOKEN:
    logger.error("❌ VERIFY_TOKEN not found in environment variables!")
    raise ValueError("VERIFY_TOKEN is required. Please check your .env file.")

# Gemini API Configuration
USER_TIMEZONE = os.getenv("USER_TIMEZONE", "Asia/Karachi")
MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.0-flash-exp")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("❌ GEMINI_API_KEY not found in environment variables!")
    raise ValueError("GEMINI_API_KEY is required. Please check your .env file.")

genai.configure(api_key=GEMINI_API_KEY)

# Google Calendar
calendar_service = None
SCOPES = ['https://www.googleapis.com/auth/calendar']


# ---------------- GOOGLE CALENDAR SETUP ----------------
def setup_google_calendar():
    """Setup Google Calendar service with OAuth or Service Account"""
    global calendar_service
    creds = None

    logger.info("📅 Setting up Google Calendar integration...")
    
    # Get OAuth credentials file from environment or use default
    oauth_file = os.getenv("GOOGLE_OAUTH_CREDENTIALS_FILE", 
                          'client_secret_428819923956-is6irhla4qp3phl2ij7ik2vv9cpecd4p.apps.googleusercontent.com.json')
    
    # Get token pickle file from environment or use default
    token_pickle_file = os.getenv("GOOGLE_TOKEN_PICKLE_FILE", 'token.pickle')
    
    if os.path.exists(oauth_file):
        logger.info("📄 Found OAuth credentials file")
        
        if os.path.exists(token_pickle_file):
            logger.info("🔑 Loading saved tokens...")
            with open(token_pickle_file, 'rb') as token:
                creds = pickle.load(token)

        if creds and creds.expired and creds.refresh_token:
            try:
                logger.info("🔄 Refreshing expired credentials...")
                creds.refresh(GoogleRequest())
                logger.info("✅ Credentials refreshed successfully")
            except Exception as e:
                logger.error(f"❌ Failed to refresh credentials: {e}")
                creds = None

        if not creds or not creds.valid:
            logger.warning("⚠️  OAuth credentials missing/invalid")
            logger.warning("💡 Run: python setup_calendar.py")
            return False

        # Save refreshed credentials
        try:
            with open(token_pickle_file, 'wb') as token:
                pickle.dump(creds, token)
        except Exception as e:
            logger.error(f"❌ Failed to save credentials: {e}")

    elif os.path.exists("credentials.json"):
        try:
            logger.info("📄 Using Service Account credentials")
            creds = service_account.Credentials.from_service_account_file(
                "credentials.json", scopes=SCOPES
            )
            logger.info("✅ Service Account loaded successfully")
        except Exception as e:
            logger.error(f"❌ Failed to load service account: {e}")
            return False

    if creds and creds.valid:
        try:
            calendar_service = build("calendar", "v3", credentials=creds)
            logger.info("✅ Google Calendar service initialized successfully")
            logger.info("📅 Calendar integration: READY")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to build calendar service: {e}")
            return False
    else:
        logger.warning("⚠️  No valid credentials found")
        logger.warning("📅 Google Calendar: DISABLED")
        return False


# Initialize calendar service
calendar_setup_result = setup_google_calendar()
if calendar_setup_result:
    logger.info("🎉 WhatBot initialization complete - All systems ready!")
else:
    logger.warning("⚠️  WhatBot started with limited functionality (no calendar)")

startup_time = time.time() - start_time
logger.info(f"⚡ Startup completed in {startup_time:.2f} seconds")
logger.info("=" * 60)
logger.info("🤖 WHATBOT READY FOR MESSAGES")
logger.info("=" * 60)


# ---------------- WHATSAPP SENDER ----------------
@app.post("/send-text/")
async def send_text_api(to: str, message: str):
    """Send WhatsApp message manually (for testing)"""
    result = await send_text(to, message)
    return result


async def send_text(to: str, message: str):
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(WHATSAPP_URL, headers=headers, json=payload)
    return response.json()


# ---------------- WEBHOOK VERIFY ----------------
@app.get("/webhook/")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge)
    else:
        raise HTTPException(status_code=403, detail="Verification failed")


# ---------------- WEBHOOK RECEIVE ----------------
@app.post("/webhook/")
async def receive_webhook(request: Request):
    try:
        data = await request.json()
        logger.debug(f"📨 Raw webhook data: {data}")

        if "entry" in data:
            for entry in data["entry"]:
                for change in entry.get("changes", []):
                    if change.get("field") == "messages":
                        message_data = change.get("value", {})
                        
                        # Process incoming messages
                        if "messages" in message_data:
                            logger.info("💬 Processing incoming message(s)")
                            for message in message_data["messages"]:
                                await process_incoming_message(
                                    message,
                                    message_data.get("contacts", [])
                                )
                        
                        # Handle status updates (read receipts, delivered, etc.)
                        elif "statuses" in message_data:
                            logger.debug("📮 Received message status update (read receipt, delivery, etc.)")
                            # You can add status processing logic here if needed
                        
                        else:
                            logger.debug("📭 Received webhook data with no messages or statuses")

        return {"status": "success"}

    except Exception as e:
        logger.error(f"❌ Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ---------------- PROCESS MESSAGE ----------------
# Store user conversations for clarification flow
user_conversations = {}
user_management_state = {}  # Store user state for reminder management

async def process_incoming_message(message: dict, contacts: list):
    from_number = message.get("from")
    message_type = message.get("type")

    if message_type == "text":
        text_body = message.get("text", {}).get("body", "")
        
        # Get contact name if available
        contact_name = "there"
        if contacts:
            for contact in contacts:
                if contact.get("wa_id") == from_number:
                    contact_name = contact.get("profile", {}).get("name", "there")
                    break
        
        logger.info(f"👤 {contact_name} ({from_number[-4:]}****): {text_body}")

        # Check if user is asking to list/manage reminders
        if await handle_reminder_management(text_body, from_number, contact_name):
            return

        # Check if user is in a clarification conversation
        existing_data = user_conversations.get(from_number)
        
        structured = await extract_with_gemini(text_body, existing_data)

        if structured:
            # Check if reminder is complete
            missing = identify_missing_info(structured)
            
            if missing:
                # Store conversation state and ask for clarification
                logger.info(f"🔄 Requesting clarification from {contact_name} for: {missing}")
                user_conversations[from_number] = structured
                question = generate_clarification_question(missing)
                
                # Enhanced clarification message
                response_msg = f"Hi {contact_name} 👋\n\n"
                response_msg += f"I'm setting up your reminder and need a bit more information:\n\n"
                
                # Show current reminder state
                response_msg += "📝 Current Reminder:\n"
                if structured.get('task'):
                    response_msg += f"   Task: {structured['task']}\n"
                else:
                    response_msg += f"   Task: Not specified\n"
                    
                if structured.get('date'):
                    response_msg += f"   Date: {structured['date']}\n"
                else:
                    response_msg += f"   Date: Not specified\n"
                    
                if structured.get('time'):
                    response_msg += f"   Time: {structured['time']}\n"
                else:
                    response_msg += f"   Time: Not specified\n"
                
                if structured.get('recurrence') and structured['recurrence'] != 'none':
                    response_msg += f"   Repeat: {structured['recurrence']}\n"
                
                response_msg += f"\n{question}\n\n"
                response_msg += "Just reply with the missing information and I'll complete your reminder."
                
                await send_text(from_number, response_msg)
                return
            
            # Reminder is complete, clear conversation and create reminder
            if from_number in user_conversations:
                del user_conversations[from_number]
            
            logger.info(f"✅ Creating reminder for {contact_name}: {structured.get('task', 'Unknown task')}")
            
            # Create calendar event
            if calendar_service:
                event_link = create_calendar_event(structured)
                calendar_msg = f"Google Calendar: Event created successfully.\nLink: {event_link}"
                logger.info(f"📅 Calendar event created: {event_link}")
            else:
                calendar_msg = "Google Calendar: Not configured (reminder saved locally)"
                logger.warning("📅 Calendar not available - reminder saved locally only")

            # Enhanced success message
            ack_msg = f"✅ Reminder Set Successfully\n\n"
            ack_msg += f"Hi {contact_name}! Your reminder has been created with the following details:\n\n"
            
            # Reminder details
            ack_msg += "📋 Reminder Details:\n"
            task_name = structured.get('task', structured.get('title', 'Unknown task'))
            ack_msg += f"   Task: {task_name}\n"
            
            if structured.get('date'):
                # Format date nicely
                try:
                    date_obj = datetime.datetime.strptime(structured['date'], "%Y-%m-%d")
                    formatted_date = date_obj.strftime("%A, %B %d, %Y")
                    ack_msg += f"   Date: {formatted_date}\n"
                except ValueError:
                    ack_msg += f"   Date: {structured['date']}\n"
            
            if structured.get('time') and structured.get('time') != 'skip':
                # Format time nicely
                try:
                    time_obj = datetime.datetime.strptime(structured['time'], "%H:%M")
                    formatted_time = time_obj.strftime("%I:%M %p")
                    ack_msg += f"   Time: {formatted_time}\n"
                except ValueError:
                    ack_msg += f"   Time: {structured['time']}\n"
            elif structured.get('time') == 'skip':
                ack_msg += f"   Time: All-day reminder\n"
            
            if structured.get('recurrence') and structured['recurrence'] != 'none':
                ack_msg += f"   Repeat: {structured['recurrence'].title()}\n"
            
            if structured.get('day_of_week'):
                ack_msg += f"   Day: {structured['day_of_week']}\n"
            
            if structured.get('notes'):
                ack_msg += f"   Notes: {structured['notes']}\n"
            
            ack_msg += f"\n{calendar_msg}\n\n"
            ack_msg += "I'll make sure to remind you! Have a great day 😊"
            
            await send_text(from_number, ack_msg)
            
        else:
            # Failed to parse - clear any existing conversation and provide helpful guidance
            if from_number in user_conversations:
                del user_conversations[from_number]
            
            logger.warning(f"❓ Could not parse reminder request from {contact_name}: '{text_body}'")
            
            error_msg = f"Hi {contact_name} 👋\n\n"
            error_msg += "I couldn't understand your reminder request. Let me help you.\n\n"
            error_msg += "Try examples like:\n"
            error_msg += "   • 'Remind me to call mom tomorrow at 3pm'\n"
            error_msg += "   • 'Doctor appointment on December 15'\n"
            error_msg += "   • 'Take medicine daily at 8am'\n"
            error_msg += "   • 'Team meeting every Monday at 10am'\n"
            error_msg += "   • 'Pay rent on 1st of every month'\n\n"
            error_msg += "📅 Or manage your reminders:\n"
            error_msg += "   • 'List my reminders today'\n"
            error_msg += "   • 'Show reminders for tomorrow'\n"
            error_msg += "   • 'What do I have next Monday'\n"
            error_msg += "   • 'My schedule this week'\n"
            error_msg += "   • 'Show agenda for December 15'\n"
            error_msg += "   • 'What's on my calendar next month'\n"
            error_msg += "   • 'Delete all reminders'\n\n"
            error_msg += "Or just tell me:\n"
            error_msg += "   • What you want to be reminded about\n"
            error_msg += "   • When you want the reminder\n"
            error_msg += "   • Any specific time (optional)\n\n"
            error_msg += "Try again and I'll help you set up your reminder."
            
            await send_text(from_number, error_msg)


# ---------------- REMINDER MANAGEMENT ----------------
async def handle_reminder_management(text_body: str, from_number: str, contact_name: str):
    """Enhanced reminder management with intelligent date parsing"""
    import re
    
    if not calendar_service:
        return False
    
    text_lower = text_body.lower().strip()
    
    # Enhanced keywords for listing reminders
    list_keywords = [
        'list', 'show', 'display', 'what are my', 'my reminders', 'reminders for',
        'schedule', 'agenda', 'what do i have', 'appointments', 'events',
        'what\'s on', 'check my', 'see my', 'view my'
    ]
    
    # Check if user wants to delete all reminders
    delete_all_keywords = [
        'delete all reminders', 'remove all reminders', 'clear all reminders', 
        'delete all my reminders', 'remove all my reminders', 'clear everything',
        'delete everything', 'remove everything'
    ]
    is_delete_all_request = any(keyword in text_lower for keyword in delete_all_keywords)
    
    # Check if user wants to list reminders
    is_list_request = any(keyword in text_lower for keyword in list_keywords)
    
    # Also check for date-specific patterns that indicate listing
    date_list_patterns = [
        r'reminders?\s+(?:for\s+|on\s+)?(.+)',
        r'what.+(?:today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
        r'(?:show|list|display).+(?:today|tomorrow|this week|next week|this month)',
        r'agenda\s+(?:for\s+)?(.+)',
        r'schedule\s+(?:for\s+)?(.+)',
        r'what.+(?:january|february|march|april|may|june|july|august|september|october|november|december)',
        r'events?\s+(?:for\s+|on\s+)?(.+)'
    ]
    
    for pattern in date_list_patterns:
        if re.search(pattern, text_lower):
            is_list_request = True
            break
    
    # Check if user is in management mode
    management_state = user_management_state.get(from_number)
    
    if management_state:
        return await handle_management_action(text_body, from_number, contact_name, management_state)
    
    if is_delete_all_request:
        # Handle delete all reminders request
        await handle_delete_all_reminders(from_number, contact_name)
        return True
    
    if is_list_request:
        # Enhanced date parsing from the request
        target_date = parse_date_from_text(text_lower)
        date_range = None
        
        # Check for range queries
        if any(phrase in text_lower for phrase in ['this week', 'next week', 'last week']):
            date_range = get_week_range(text_lower)
        elif any(phrase in text_lower for phrase in ['this month', 'next month', 'last month']):
            date_range = get_month_range(text_lower)
        
        # Default to today if no date found
        if not target_date and not date_range:
            target_date = datetime.datetime.now(pytz.timezone(USER_TIMEZONE)).strftime("%Y-%m-%d")
        
        # Get reminders
        if date_range:
            reminders = get_reminders_for_date_range(date_range['start'], date_range['end'])
            await display_range_reminders(from_number, contact_name, reminders, date_range)
        else:
            reminders = get_reminders_for_date(target_date)
            if not reminders:
                formatted_date = format_date_friendly(target_date)
                msg = f"Hi {contact_name} 👋\n\n"
                msg += f"📅 You have no reminders scheduled for {formatted_date}.\n\n"
                msg += "Want to create one? Just tell me:\n"
                msg += "   • 'Remind me to call mom at 3pm'\n"
                msg += "   • 'Doctor appointment tomorrow'\n"
                msg += "   • 'Team meeting next Monday'\n\n"
                msg += "Or try asking about other dates:\n"
                msg += "   • 'Show my reminders for tomorrow'\n"
                msg += "   • 'What's my schedule this week'\n"
                msg += "   • 'List reminders for December 15'"
                
                await send_text(from_number, msg)
                return True
            
            # Display reminders with management options
            await display_reminders_with_actions(from_number, contact_name, reminders, target_date)
        
        return True
    
    return False

async def handle_delete_all_reminders(from_number: str, contact_name: str):
    """Handle delete all reminders request"""
    try:
        # Get all reminders for the next 30 days to cover most user reminders
        now = datetime.datetime.now(pytz.timezone(USER_TIMEZONE))
        start_date = now.strftime("%Y-%m-%d")
        end_date = (now + timedelta(days=30)).strftime("%Y-%m-%d")
        
        all_reminders = get_reminders_for_date_range(start_date, end_date)
        
        if not all_reminders:
            msg = f"Hi {contact_name} 👋\n\n"
            msg += "📅 You have no reminders to delete.\n\n"
            msg += "You can create new reminders anytime by telling me what you need to remember."
            await send_text(from_number, msg)
            return
        
        # Delete all reminders
        deleted_count = 0
        failed_count = 0
        
        for reminder in all_reminders:
            if delete_calendar_event(reminder['id']):
                deleted_count += 1
            else:
                failed_count += 1
        
        # Send confirmation message
        msg = f"Hi {contact_name} 👋\n\n"
        if deleted_count > 0:
            msg += f"✅ Successfully deleted {deleted_count} reminder{'s' if deleted_count != 1 else ''}.\n\n"
        
        if failed_count > 0:
            msg += f"❌ Failed to delete {failed_count} reminder{'s' if failed_count != 1 else ''}. Please try again later.\n\n"
        
        msg += "You can create new reminders anytime."
        
        await send_text(from_number, msg)
        
    except Exception as e:
        logger.error(f"Error deleting all reminders: {str(e)}")
        msg = f"Hi {contact_name}.\n\n"
        msg += "Sorry, I encountered an error while deleting your reminders. Please try again later."
        await send_text(from_number, msg)

async def handle_management_action(text_body: str, from_number: str, contact_name: str, management_state: dict):
    """Handle edit/delete actions on specific reminders"""
    text_lower = text_body.lower().strip()
    
    logger.info(f"Handle management action: {from_number}, mode: {management_state.get('mode')}, input: '{text_body}'")
    
    # Handle cancellation
    if text_lower in ['cancel', 'exit', 'done', 'back']:
        del user_management_state[from_number]
        await send_text(from_number, "Management mode exited. You can create new reminders or list them again.")
        return True
    
    # Handle number selection - check current mode first
    try:
        selection = int(text_lower)
        
        # If we're in listing mode, select a reminder
        if management_state.get('mode') == 'listing':
            reminders = management_state.get('reminders', [])
            
            if 1 <= selection <= len(reminders):
                selected_reminder = reminders[selection - 1]
                
                # Ask what to do with this reminder
                user_management_state[from_number] = {
                    'mode': 'action_selected',
                    'selected_reminder': selected_reminder,
                    'reminders': reminders,
                    'date': management_state.get('date')
                }
                
                logger.info(f"Set management state for {from_number}: mode=action_selected, reminder={selected_reminder['summary']}")
                
                msg = f"📝 Selected Reminder:\n"
                msg += f"   Task: {selected_reminder['summary']}\n"
                msg += f"   Time: {format_event_datetime(selected_reminder)}\n\n"
                msg += "What would you like to do?\n"
                msg += "   1 - ✏️ Edit this reminder\n"
                msg += "   2 - 🗑️ Delete this reminder\n"
                msg += "   3 - ↩️ Cancel and go back\n\n"
                msg += "Reply with 1, 2, or 3."
                
                await send_text(from_number, msg)
                return True
            else:
                await send_text(from_number, f"Please enter a number between 1 and {len(reminders)}, or 'cancel' to exit.")
                return True
        
        # If we're in action_selected mode, handle the action choice
        elif management_state.get('mode') == 'action_selected':
            if selection == 1:
                # Edit
                selected = management_state['selected_reminder']
                user_management_state[from_number] = {
                    'mode': 'editing',
                    'selected_reminder': selected,
                    'reminders': management_state['reminders'],
                    'date': management_state.get('date')
                }
                
                msg = f"Editing Reminder:\n"
                msg += f"   Current: {selected['summary']}\n"
                msg += f"   Time: {format_event_datetime(selected)}\n\n"
                msg += "Tell me what to change:\n"
                msg += "   • 'Change time to 4pm'\n"
                msg += "   • 'Move to tomorrow'\n"
                msg += "   • 'Rename to call doctor'\n"
                msg += "   • 'Make it daily'\n\n"
                msg += "Or describe the new reminder details."
                
                await send_text(from_number, msg)
                return True
                
            elif selection == 2:
                # Delete
                selected = management_state['selected_reminder']
                logger.info(f"Attempting to delete reminder with ID: {selected.get('id')}")
                
                success = delete_calendar_event(selected['id'])
                
                # Clear management state
                del user_management_state[from_number]
                
                if success:
                    msg = f"🗑️ Reminder Deleted Successfully.\n\n"
                    msg += f"Removed: {selected['summary']}\n"
                    msg += f"Was scheduled for: {format_event_datetime(selected)}\n\n"
                    msg += "You can create new reminders anytime or list your remaining ones."
                else:
                    msg = f"❌ Failed to delete the reminder. Please try again later or contact support."
                
                await send_text(from_number, msg)
                return True
                
            elif selection == 3:
                # Go back to reminder list
                reminders = management_state['reminders']
                target_date = management_state.get('date', datetime.datetime.now(pytz.timezone(USER_TIMEZONE)).strftime("%Y-%m-%d"))
                
                user_management_state[from_number] = {
                    'mode': 'listing',
                    'reminders': reminders,
                    'date': target_date
                }
                
                await display_reminders_with_actions(from_number, contact_name, reminders, target_date)
                return True
            else:
                await send_text(from_number, "Please enter 1, 2, or 3.")
                return True
            
    except ValueError:
        # Handle text-based commands when not expecting numbers
        if management_state.get('mode') == 'editing':
            # Process edit instructions
            selected = management_state['selected_reminder']
            
            # Use Gemini to understand the edit request
            edit_result = await process_reminder_edit(text_body, selected)
            
            if edit_result:
                success = update_calendar_event(selected['id'], edit_result)
                
                # Clear management state
                del user_management_state[from_number]
                
                if success:
                    msg = f"✅ Reminder Updated Successfully.\n\n"
                    msg += f"📋 New Details:\n"
                    msg += f"   Task: {edit_result.get('summary', selected['summary'])}\n"
                    
                    # Show updated date/time
                    if 'start' in edit_result:
                        if 'dateTime' in edit_result['start']:
                            dt = datetime.datetime.fromisoformat(edit_result['start']['dateTime'].replace('Z', '+00:00'))
                            local_dt = dt.astimezone(pytz.timezone(USER_TIMEZONE))
                            msg += f"   Date: {local_dt.strftime('%A, %B %d, %Y')}\n"
                            msg += f"   Time: {local_dt.strftime('%I:%M %p')}\n"
                        else:
                            msg += f"   Date: {edit_result['start']['date']} (All-day)\n"
                    
                    msg += f"\nYour reminder has been updated successfully."
                else:
                    msg = f"❌ Failed to update the reminder. Please try again later."
                
                await send_text(from_number, msg)
                return True
            else:
                msg = f"I couldn't understand how to edit the reminder.\n\n"
                msg += "Try being more specific:\n"
                msg += "   • 'Change time to 4pm'\n"
                msg += "   • 'Move to next Monday'\n"
                msg += "   • 'Rename to doctor appointment'\n\n"
                msg += "Or type 'cancel' to go back."
                
                await send_text(from_number, msg)
                return True
        
        # For other modes, provide appropriate guidance
        elif management_state.get('mode') == 'listing':
            reminders = management_state.get('reminders', [])
            await send_text(from_number, f"Please enter a number between 1 and {len(reminders)}, or 'cancel' to exit.")
        elif management_state.get('mode') == 'action_selected':
            await send_text(from_number, "Please enter 1 (Edit), 2 (Delete), or 3 (Cancel).")
        else:
            await send_text(from_number, f"I didn't understand that. Please try again or type 'cancel' to exit.")
    
    return True

def parse_date_from_text(text: str):
    """Enhanced date parsing from natural language text"""
    now = datetime.datetime.now(pytz.timezone(USER_TIMEZONE))
    text_lower = text.lower()
    
    # Basic relative dates
    if 'today' in text_lower:
        return now.strftime("%Y-%m-%d")
    elif 'tomorrow' in text_lower:
        return (now + timedelta(days=1)).strftime("%Y-%m-%d")
    elif 'yesterday' in text_lower:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Day of week patterns
    weekdays = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6,
        'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6
    }
    
    # Check for specific weekdays
    for day_name, day_num in weekdays.items():
        if day_name in text_lower:
            current_weekday = now.weekday()
            
            # Check for "next [day]" or "this [day]"
            if 'next' in text_lower:
                days_ahead = (day_num - current_weekday + 7) % 7
                if days_ahead == 0:  # If it's the same day, go to next week
                    days_ahead = 7
                target_date = now + timedelta(days=days_ahead)
                return target_date.strftime("%Y-%m-%d")
            elif 'this' in text_lower or 'coming' in text_lower:
                days_ahead = (day_num - current_weekday) % 7
                if days_ahead == 0 and 'this' in text_lower:  # Today
                    target_date = now
                else:
                    target_date = now + timedelta(days=days_ahead)
                return target_date.strftime("%Y-%m-%d")
            elif 'last' in text_lower or 'previous' in text_lower:
                days_back = (current_weekday - day_num) % 7
                if days_back == 0:  # Same day, go to previous week
                    days_back = 7
                target_date = now - timedelta(days=days_back)
                return target_date.strftime("%Y-%m-%d")
            else:
                # Default to next occurrence of this weekday
                days_ahead = (day_num - current_weekday) % 7
                if days_ahead == 0:  # If it's today, assume next week
                    days_ahead = 7
                target_date = now + timedelta(days=days_ahead)
                return target_date.strftime("%Y-%m-%d")
                target_date = now + timedelta(days=days_ahead)
                return target_date.strftime("%Y-%m-%d")
    
    # Week-based patterns
    if 'this week' in text_lower:
        days_since_monday = now.weekday()
        monday = now - timedelta(days=days_since_monday)
        return monday.strftime("%Y-%m-%d")
    elif 'next week' in text_lower:
        return (now + timedelta(weeks=1)).strftime("%Y-%m-%d")
    elif 'last week' in text_lower:
        return (now - timedelta(weeks=1)).strftime("%Y-%m-%d")
    
    # Month-based patterns
    if 'this month' in text_lower:
        return now.replace(day=1).strftime("%Y-%m-%d")
    elif 'next month' in text_lower:
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1)
        else:
            next_month = now.replace(month=now.month + 1, day=1)
        return next_month.strftime("%Y-%m-%d")
    elif 'last month' in text_lower:
        if now.month == 1:
            last_month = now.replace(year=now.year - 1, month=12, day=1)
        else:
            last_month = now.replace(month=now.month - 1, day=1)
        return last_month.strftime("%Y-%m-%d")
    
    # Relative day patterns
    
    # "in X days" or "X days from now"
    days_pattern = r'(?:in\s+)?(\d+)\s+days?(?:\s+from\s+now)?'
    match = re.search(days_pattern, text_lower)
    if match:
        days = int(match.group(1))
        target_date = now + timedelta(days=days)
        return target_date.strftime("%Y-%m-%d")
    
    # "X days ago"
    ago_pattern = r'(\d+)\s+days?\s+ago'
    match = re.search(ago_pattern, text_lower)
    if match:
        days = int(match.group(1))
        target_date = now - timedelta(days=days)
        return target_date.strftime("%Y-%m-%d")
    
    # Date formats like "10/15", "15-10", "2025-10-15"
    date_patterns = [
        r'(\d{4})-(\d{1,2})-(\d{1,2})',  # YYYY-MM-DD
        r'(\d{1,2})/(\d{1,2})/(\d{4})',  # MM/DD/YYYY
        r'(\d{1,2})/(\d{1,2})',          # MM/DD (current year)
        r'(\d{1,2})-(\d{1,2})-(\d{4})',  # MM-DD-YYYY or DD-MM-YYYY
        r'(\d{1,2})-(\d{1,2})',          # MM-DD or DD-MM (current year)
    ]
    
    for i, pattern in enumerate(date_patterns):
        match = re.search(pattern, text)
        if match:
            try:
                if i == 0:  # YYYY-MM-DD
                    year, month, day = map(int, match.groups())
                elif i in [1, 3]:  # MM/DD/YYYY or MM-DD-YYYY (assume MM/DD format)
                    month, day, year = map(int, match.groups())
                else:  # MM/DD or MM-DD (current year, assume MM/DD format)
                    month, day = map(int, match.groups())
                    year = now.year
                    # If date has passed this year, assume next year
                    test_date = datetime.date(year, month, day)
                    if test_date < now.date():
                        year += 1
                
                # Validate date
                test_date = datetime.date(year, month, day)
                return test_date.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                continue
    
    # Month name patterns
    month_patterns = [
        r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{4}))?',
        r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{4}))?',
        r'(\d{1,2})(?:st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december)(?:\s*,?\s*(\d{4}))?',
        r'(\d{1,2})(?:st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(?:\s*,?\s*(\d{4}))?'
    ]
    
    month_map = {
        'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
        'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6,
        'july': 7, 'jul': 7, 'august': 8, 'aug': 8, 'september': 9, 'sep': 9,
        'october': 10, 'oct': 10, 'november': 11, 'nov': 11, 'december': 12, 'dec': 12
    }
    
    for i, pattern in enumerate(month_patterns):
        match = re.search(pattern, text_lower)
        if match:
            try:
                groups = match.groups()
                if i < 2:  # Month first
                    month_name, day_str, year_str = groups
                    day = int(day_str)
                else:  # Day first
                    day_str, month_name, year_str = groups
                    day = int(day_str)
                
                month = month_map.get(month_name.lower())
                year = int(year_str) if year_str else now.year
                
                if month and 1 <= day <= 31:
                    # If no year specified and date has passed, use next year
                    if not year_str:
                        test_date = datetime.date(year, month, day)
                        if test_date < now.date():
                            year += 1
                    
                    test_date = datetime.date(year, month, day)
                    return test_date.strftime("%Y-%m-%d")
            except (ValueError, KeyError):
                continue
    
    return None

def get_week_range(text: str):
    """Get start and end dates for week-based queries"""
    now = datetime.datetime.now(pytz.timezone(USER_TIMEZONE))
    
    if 'this week' in text.lower():
        # Start from Monday of current week
        days_since_monday = now.weekday()
        start_date = now - timedelta(days=days_since_monday)
        end_date = start_date + timedelta(days=6)  # Sunday
    elif 'next week' in text.lower():
        # Start from Monday of next week
        days_since_monday = now.weekday()
        start_date = now - timedelta(days=days_since_monday) + timedelta(weeks=1)
        end_date = start_date + timedelta(days=6)
    elif 'last week' in text.lower():
        # Start from Monday of last week
        days_since_monday = now.weekday()
        start_date = now - timedelta(days=days_since_monday) - timedelta(weeks=1)
        end_date = start_date + timedelta(days=6)
    else:
        return None
    
    return {
        'start': start_date.strftime("%Y-%m-%d"),
        'end': end_date.strftime("%Y-%m-%d"),
        'type': 'week'
    }

def get_month_range(text: str):
    """Get start and end dates for month-based queries"""
    now = datetime.datetime.now(pytz.timezone(USER_TIMEZONE))
    
    if 'this month' in text.lower():
        start_date = now.replace(day=1)
        # Last day of current month
        if now.month == 12:
            end_date = now.replace(year=now.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = now.replace(month=now.month + 1, day=1) - timedelta(days=1)
    elif 'next month' in text.lower():
        if now.month == 12:
            start_date = now.replace(year=now.year + 1, month=1, day=1)
            end_date = start_date.replace(month=2, day=1) - timedelta(days=1)
        else:
            start_date = now.replace(month=now.month + 1, day=1)
            if start_date.month == 12:
                end_date = start_date.replace(year=start_date.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_date = start_date.replace(month=start_date.month + 1, day=1) - timedelta(days=1)
    elif 'last month' in text.lower():
        if now.month == 1:
            start_date = now.replace(year=now.year - 1, month=12, day=1)
            end_date = now.replace(day=1) - timedelta(days=1)
        else:
            start_date = now.replace(month=now.month - 1, day=1)
            end_date = now.replace(day=1) - timedelta(days=1)
    else:
        return None
    
    return {
        'start': start_date.strftime("%Y-%m-%d"),
        'end': end_date.strftime("%Y-%m-%d"),
        'type': 'month'
    }

async def display_range_reminders(from_number: str, contact_name: str, reminders: list, date_range: dict):
    """Display reminders for a date range (week/month)"""
    range_type = date_range['type']
    start_formatted = format_date_friendly(date_range['start'])
    end_formatted = format_date_friendly(date_range['end'])
    
    if range_type == 'week':
        title = f"📅 Your Reminders This Week"
        subtitle = f"({start_formatted} to {end_formatted})"
    else:  # month
        title = f"📅 Your Reminders This Month"
        subtitle = f"({start_formatted} to {end_formatted})"
    
    if not reminders:
        msg = f"{title}\n\n"
        msg += f"Hi {contact_name} 👋\n\n"
        msg += f"You have no reminders scheduled for {subtitle.lower()}.\n\n"
        msg += "Want to create some? Try:\n"
        msg += "   • 'Remind me to call mom tomorrow at 3pm'\n"
        msg += "   • 'Meeting every Monday at 10am'\n"
        msg += "   • 'Doctor appointment next Friday'"
        
        await send_text(from_number, msg)
        return
    
    # Group reminders by date
    reminders_by_date = {}
    for reminder in reminders:
        start = reminder.get('start', {})
        if 'dateTime' in start:
            dt = datetime.datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
            local_dt = dt.astimezone(pytz.timezone(USER_TIMEZONE))
            date_key = local_dt.strftime("%Y-%m-%d")
        elif 'date' in start:
            date_key = start['date']
        else:
            date_key = "unknown"
        
        if date_key not in reminders_by_date:
            reminders_by_date[date_key] = []
        reminders_by_date[date_key].append(reminder)
    
    msg = f"{title}\n{subtitle}\n\n"
    msg += f"Hi {contact_name} 👋, here are your scheduled reminders:\n\n"
    
    # Sort dates and display
    sorted_dates = sorted(reminders_by_date.keys())
    for date_key in sorted_dates:
        if date_key == "unknown":
            continue
        
        date_reminders = reminders_by_date[date_key]
        friendly_date = format_date_friendly(date_key)
        
        msg += f"📆 {friendly_date}:\n"
        for i, reminder in enumerate(date_reminders, 1):
            time_str = format_event_datetime(reminder)
            # Extract just the time part for cleaner display
            if " at " in time_str:
                time_part = time_str.split(" at ")[1]
                msg += f"   {i}. {reminder['summary']} - {time_part}\n"
            else:
                msg += f"   {i}. {reminder['summary']} - {time_str}\n"
        msg += "\n"
    
    msg += "💡 To manage specific reminders, try:\n"
    msg += "   • 'Show reminders for [specific date]'\n"
    msg += "   • 'List my reminders today'\n"
    msg += "   • 'What do I have tomorrow'"
    
    await send_text(from_number, msg)

def get_reminders_for_date(date_str: str):
    """Get all calendar events for a specific date"""
    if not calendar_service:
        return []
    
    try:
        # Convert date to start and end of day
        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        tz = pytz.timezone(USER_TIMEZONE)
        
        start_of_day = tz.localize(date_obj.replace(hour=0, minute=0, second=0))
        end_of_day = tz.localize(date_obj.replace(hour=23, minute=59, second=59))
        
        # Query calendar events
        events_result = calendar_service.events().list(
            calendarId='primary',
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            singleEvents=True,
            orderBy='startTime',
            maxResults=50
        ).execute()
        
        events = events_result.get('items', [])
        
        # Filter to only include events that look like reminders
        reminders = []
        for event in events:
            # Include events that have our typical reminder characteristics
            # or any event that the user might want to manage
            if event.get('summary'):
                reminders.append(event)
        
        return reminders
        
    except Exception as e:
        logger.error(f"Error fetching calendar events: {str(e)}")
        return []

def get_reminders_for_date_range(start_date: str, end_date: str):
    """Get all calendar events for a date range (for weekly/monthly views)"""
    if not calendar_service:
        return []
    
    try:
        start_obj = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        end_obj = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        tz = pytz.timezone(USER_TIMEZONE)
        
        start_of_period = tz.localize(start_obj.replace(hour=0, minute=0, second=0))
        end_of_period = tz.localize(end_obj.replace(hour=23, minute=59, second=59))
        
        events_result = calendar_service.events().list(
            calendarId='primary',
            timeMin=start_of_period.isoformat(),
            timeMax=end_of_period.isoformat(),
            singleEvents=True,
            orderBy='startTime',
            maxResults=100
        ).execute()
        
        return events_result.get('items', [])
        
    except Exception as e:
        logger.error(f"Error fetching calendar events for range: {str(e)}")
        return []

async def display_reminders_with_actions(from_number: str, contact_name: str, reminders: list, target_date: str):
    """Display reminders with numbered options for management"""
    formatted_date = format_date_friendly(target_date)
    
    msg = f"📅 Your Reminders for {formatted_date}\n\n"
    msg += f"Hi {contact_name} 👋, here are your scheduled reminders:\n\n"
    
    for i, reminder in enumerate(reminders, 1):
        msg += f"{i}. {reminder['summary']}\n"
        msg += f"   ⏰ {format_event_datetime(reminder)}\n\n"
    
    msg += "\n\n\n🔧 Management Options:\n"
    msg += f"   Reply with a number (1-{len(reminders)}) to edit or delete\n"
    msg += f"   Reply 'cancel' to exit management mode\n\n"
    msg += "What would you like to do with these reminders?"
    
    # Store management state - EXPLICITLY set mode to 'listing'
    user_management_state[from_number] = {
        'mode': 'listing',
        'reminders': reminders,
        'date': target_date
    }
    
    logger.info(f"Set management state for {from_number}: mode=listing, {len(reminders)} reminders")
    
    await send_text(from_number, msg)

def format_date_friendly(date_str: str):
    """Convert YYYY-MM-DD to friendly format"""
    try:
        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        today = datetime.datetime.now(pytz.timezone(USER_TIMEZONE)).date()
        
        if date_obj.date() == today:
            return "Today"
        elif date_obj.date() == today + timedelta(days=1):
            return "Tomorrow"
        elif date_obj.date() == today - timedelta(days=1):
            return "Yesterday"
        else:
            return date_obj.strftime("%A, %B %d, %Y")
    except (ValueError, TypeError):
        return date_str

def format_event_datetime(event: dict):
    """Format event datetime for display"""
    try:
        start = event.get('start', {})
        if 'dateTime' in start:
            # Timed event
            dt = datetime.datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
            local_dt = dt.astimezone(pytz.timezone(USER_TIMEZONE))
            return f"{local_dt.strftime('%A, %B %d')} at {local_dt.strftime('%I:%M %p')}"
        elif 'date' in start:
            # All-day event
            date_obj = datetime.datetime.strptime(start['date'], "%Y-%m-%d")
            return f"{date_obj.strftime('%A, %B %d')} - All-day"
        else:
            return "Date/time not specified"
    except Exception as e:
        logger.error(f"Error formatting event datetime: {str(e)}")
        return "Unable to parse date/time"

async def process_reminder_edit(edit_text: str, original_event: dict):
    """Use Gemini to understand edit instructions and return updated event data"""
    model = genai.GenerativeModel(MODEL_NAME)
    date_context = get_current_date_context()
    
    # Extract current event details
    current_summary = original_event.get('summary', '')
    current_start = original_event.get('start', {})
    
    prompt = f"""
You are helping to edit a calendar reminder. The user wants to modify an existing event.

Current Event:
- Summary: "{current_summary}"
- Start: {json.dumps(current_start)}

User's edit instruction: "{edit_text}"

Context:
- Today is {date_context['current_day']}, {date_context['current_date']}
- Current time: {date_context['current_time']}
- User timezone: {USER_TIMEZONE}

Return ONLY a JSON object with the fields that should be updated. Only include fields that are being changed.

Possible fields to update:
{{
  "summary": "new task name",
  "start": {{"dateTime": "YYYY-MM-DDTHH:MM:SS", "timeZone": "{USER_TIMEZONE}"}},
  "end": {{"dateTime": "YYYY-MM-DDTHH:MM:SS", "timeZone": "{USER_TIMEZONE}"}},
  "recurrence": ["RRULE:FREQ=DAILY"] // for recurring events
}}

For all-day events use:
"start": {{"date": "YYYY-MM-DD"}}
"end": {{"date": "YYYY-MM-DD"}}

Rules:
1. Only include fields that are being changed
2. If changing time, include both start and end
3. For date changes: 'tomorrow' = {(datetime.datetime.now(pytz.timezone(USER_TIMEZONE)) + timedelta(days=1)).strftime("%Y-%m-%d")}
4. Convert times to 24-hour format with timezone
5. Return ONLY the JSON object, no explanation
"""

    try:
        resp = model.generate_content(
            contents=[{"parts": [{"text": prompt}]}],
            generation_config={
                "max_output_tokens": 300,
                "temperature": 0.1,
                "top_p": 0.95
            }
        )

        if not resp.candidates or not resp.candidates[0].content.parts:
            return None

        text = resp.candidates[0].content.parts[0].text.strip()
        
        # Clean markdown formatting
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'^```\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        text = text.strip()

        # Parse JSON
        updates = json.loads(text)
        
        # Validate and format the updates
        if 'start' in updates and 'end' not in updates:
            # If start time is updated, update end time too
            start_data = updates['start']
            if 'dateTime' in start_data:
                # For timed events, make end time same as start (reminder duration = 0)
                updates['end'] = start_data.copy()
            elif 'date' in start_data:
                # For all-day events, end date should be same as start date
                updates['end'] = start_data.copy()
        
        logger.info(f"Processed edit: {updates}")
        return updates

    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Error processing reminder edit: {str(e)}")
        return None

def update_calendar_event(event_id: str, updates: dict):
    """Update a calendar event with new data"""
    if not calendar_service:
        return False
    
    try:
        # First get the current event
        current_event = calendar_service.events().get(
            calendarId='primary',
            eventId=event_id
        ).execute()
        
        # Apply updates to the current event
        for key, value in updates.items():
            current_event[key] = value
        
        # Update the event
        updated_event = calendar_service.events().update(
            calendarId='primary',
            eventId=event_id,
            body=current_event
        ).execute()
        
        logger.info(f"✅ Calendar event updated successfully: {event_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error updating calendar event: {str(e)}")
        return False

def delete_calendar_event(event_id: str):
    """Delete a calendar event"""
    if not calendar_service:
        logger.error("❌ Calendar service not available for deletion")
        return False
    
    if not event_id:
        logger.error("No event ID provided for deletion")
        return False
    
    try:
        logger.info(f"Attempting to delete calendar event with ID: {event_id}")
        
        # First check if the event exists
        try:
            calendar_service.events().get(
                calendarId='primary',
                eventId=event_id
            ).execute()
            logger.info(f"Event {event_id} exists, proceeding with deletion")
        except Exception as e:
            logger.error(f"Event {event_id} not found or not accessible: {str(e)}")
            return False
        
        # Delete the event
        calendar_service.events().delete(
            calendarId='primary',
            eventId=event_id
        ).execute()
        
        logger.info(f"Event deleted successfully: {event_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error deleting calendar event {event_id}: {str(e)}")
        return False


# ---------------- ADVANCED GEMINI PARSER ----------------
def get_current_date_context():
    """Return current date/time with timezone awareness"""
    now = datetime.datetime.now(pytz.timezone(USER_TIMEZONE))
    return {
        "current_date": now.strftime("%Y-%m-%d"),
        "current_time": now.strftime("%H:%M"),
        "current_day": now.strftime("%A")
    }

async def extract_with_gemini(user_input: str, existing_data=None):
    """Extract structured reminder JSON from user input using advanced Gemini processing"""
    model = genai.GenerativeModel(MODEL_NAME)
    date_context = get_current_date_context()

    # Check if user is declining to provide time
    user_input_lower = user_input.lower().strip()
    skip_time_phrases = ['no time', 'all day', 'whole day', 'entire day', 'skip time', 'no specific time']
    is_skipping_time = any(phrase in user_input_lower for phrase in skip_time_phrases)

    # Build context from existing data
    existing_context = ""
    if existing_data:
        existing_context = f"\nExisting reminder data:\n{json.dumps(existing_data, indent=2)}\n"

    prompt = f"""
You are a reminder extraction assistant and your name is WhatBot  . Extract reminder information and return ONLY a valid JSON object.

Context:
- Today is {date_context['current_day']}, {date_context['current_date']}
- Current time: {date_context['current_time']}
- User timezone: {USER_TIMEZONE}
- User wants to skip time: {is_skipping_time}
{existing_context}
User input: "{user_input}"

Return a JSON object with these fields:
{{
  "task": "description of the task or null",
  "date": "YYYY-MM-DD format or null",
  "time": "HH:MM in 24-hour format or null",
  "recurrence": "hourly/daily/weekly/monthly/yearly/custom or null",
  "day_of_week": "Monday/Tuesday/etc or null",
  "notes": "any extra context or null"
}}

Rules:
1. 'tomorrow' = {(datetime.datetime.now(pytz.timezone(USER_TIMEZONE)) + timedelta(days=1)).strftime("%Y-%m-%d")}
2. 'today' = {date_context['current_date']}
3. Convert times to 24-hour format (3pm = 15:00, 2:30pm = 14:30)
4. For 'next week', use approximate date: {(datetime.datetime.now(pytz.timezone(USER_TIMEZONE)) + timedelta(weeks=1)).strftime("%Y-%m-%d")}
5. For recurring tasks (every X), set recurrence field appropriately
6. If existing data is provided, merge the new information with it
7. Return ONLY the JSON object, no markdown, no explanation, no extra text.
8. If user wants to skip time, set time to "skip" to indicate all-day reminder
9. For backward compatibility, also include these legacy fields:
   - "title": same as "task"
   - If recurrence is null, set to "none"
"""

    try:
        logger.debug(f"🧠 Sending request to Gemini AI...")
        resp = model.generate_content(
            contents=[{"parts": [{"text": prompt}]}],
            generation_config={
                "max_output_tokens": 500,
                "temperature": 0.1,
                "top_p": 0.95
            }
        )

        if not resp.candidates:
            logger.error("❌ No response candidates returned from Gemini")
            return None
        
        candidate = resp.candidates[0]
        
        if not hasattr(candidate, 'content') or not candidate.content.parts:
            logger.error("❌ Empty response from Gemini model")
            return None

        text = candidate.content.parts[0].text.strip()
        logger.debug(f"🧠 Gemini raw response: {text}")

        # Clean markdown formatting
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'^```\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        text = text.strip()

        # Parse JSON
        parsed = json.loads(text)
        logger.debug(f"✅ Gemini parsed result: {parsed}")
        
        # Ensure all required fields exist
        default_structure = {
            "task": None,
            "date": None,
            "time": None,
            "recurrence": None,
            "day_of_week": None,
            "notes": None
        }
        
        # Merge with defaults
        for key in default_structure:
            if key not in parsed:
                parsed[key] = None
        
        # If existing data, merge non-null values
        if existing_data:
            for key in default_structure:
                if parsed[key] is None and existing_data.get(key) is not None:
                    parsed[key] = existing_data[key]
        
        # Handle time skipping
        if parsed.get("time") == "skip" or is_skipping_time:
            parsed["time"] = "skip"  # Special marker for all-day
        
        # Add backward compatibility fields
        parsed["title"] = parsed.get("task") or "Reminder"
        if parsed.get("recurrence") is None:
            parsed["recurrence"] = "none"
        
        # Validate date format if provided
        if parsed.get("date"):
            try:
                datetime.datetime.strptime(parsed["date"], "%Y-%m-%d")
            except ValueError:
                logger.error(f"❌ Invalid date format: {parsed['date']}")
                return None
        
        logger.info(f"✅ Successfully parsed reminder: {parsed.get('task', 'Unknown task')}")
        logger.debug(f"📋 Full parsed data: {parsed}")
        return parsed

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parsing error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"❌ Gemini parsing failed: {str(e)}")
        return None

def identify_missing_info(reminder_data):
    """Check which fields are missing"""
    missing = []
    
    if not reminder_data.get("task") and not reminder_data.get("title"):
        missing.append("task")
    
    # For recurring reminders, date is optional
    if not reminder_data.get("recurrence") or reminder_data.get("recurrence") == "none":
        if not reminder_data.get("date") and not reminder_data.get("day_of_week"):
            missing.append("date")
    
    # Check if time is needed (only ask for time if date is set and time is not "skip")
    if (reminder_data.get("date") and 
        not reminder_data.get("time") and 
        reminder_data.get("time") != "skip" and
        (not reminder_data.get("recurrence") or reminder_data.get("recurrence") == "none")):
        # Only ask for time for non-recurring, single-day reminders
        missing.append("time")
    
    return missing

def generate_clarification_question(missing_info):
    """Ask progressive clarification questions with helpful examples"""
    if not missing_info:
        return None

    if "task" in missing_info:
        return "❓ What should I remind you about?\nExamples: 'call mom', 'doctor appointment', 'take medicine', 'team meeting'"

    if "date" in missing_info:
        current_date = datetime.datetime.now(pytz.timezone(USER_TIMEZONE))
        tomorrow = (current_date + timedelta(days=1)).strftime("%B %d")
        next_week = (current_date + timedelta(days=7)).strftime("%B %d")
        
        return f"📅 When should I set this reminder?\nExamples: 'tomorrow', 'next Monday', '{tomorrow}', '{next_week}', 'December 15'"

    if "time" in missing_info:
        return "🕐 At what time should I remind you?\nExamples: '3pm', '2:30pm', '14:30', '8 in the morning'\nOr reply 'no time' for an all-day reminder"

    return "Could you provide more details about your reminder?"


# ---------------- GOOGLE CALENDAR ----------------
def create_calendar_event(structured: dict):
    if not calendar_service:
        return "Calendar not configured"

    try:
        # Get task name from either 'task' or 'title' field
        task_name = structured.get("task") or structured.get("title") or "Reminder"
        
        # Build event summary
        time_value = structured.get("time")
        if time_value and time_value != "skip":
            summary = f"{task_name} at {time_value}"
        else:
            summary = task_name
        
        # Create base event
        event = {
            "summary": summary,
        }
        
        # Handle date and time
        if structured.get("date"):
            time_value = structured.get("time")
            if time_value and time_value != "skip":
                # Specific date and time
                start_datetime = f"{structured['date']}T{time_value}:00"
                end_datetime = f"{structured['date']}T{time_value}:00"
                
                event.update({
                    "start": {
                        "dateTime": start_datetime,
                        "timeZone": USER_TIMEZONE
                    },
                    "end": {
                        "dateTime": end_datetime,
                        "timeZone": USER_TIMEZONE
                    }
                })
            else:
                # All-day event (time is None or "skip")
                event.update({
                    "start": {"date": structured["date"]},
                    "end": {"date": structured["date"]}
                })
        else:
            # No specific date, use today as all-day event
            today = datetime.datetime.now(pytz.timezone(USER_TIMEZONE)).strftime("%Y-%m-%d")
            event.update({
                "start": {"date": today},
                "end": {"date": today}
            })

        # Handle recurrence
        recurrence_value = structured.get("recurrence")
        if recurrence_value and recurrence_value != "none":
            if recurrence_value == "yearly":
                event["recurrence"] = ["RRULE:FREQ=YEARLY"]
            elif recurrence_value == "monthly":
                event["recurrence"] = ["RRULE:FREQ=MONTHLY"]
            elif recurrence_value == "weekly":
                event["recurrence"] = ["RRULE:FREQ=WEEKLY"]
            elif recurrence_value == "daily":
                event["recurrence"] = ["RRULE:FREQ=DAILY"]
            elif recurrence_value == "hourly":
                event["recurrence"] = ["RRULE:FREQ=HOURLY"]

        # Add notes if available
        notes = []
        if structured.get("notes"):
            notes.append(f"Notes: {structured['notes']}")
        if structured.get("day_of_week"):
            notes.append(f"Preferred day: {structured['day_of_week']}")
        
        if notes:
            event["description"] = "\n".join(notes)

        # Create the event
        logger.debug(f"📝 Creating calendar event: {event}")
        event_result = calendar_service.events().insert(
            calendarId="primary", body=event
        ).execute()

        event_link = event_result.get("htmlLink", "Event created but no link available")
        logger.info(f"✅ Calendar event created successfully: {task_name}")
        return event_link

    except Exception as e:
        logger.error(f"❌ Calendar event creation failed: {str(e)}")
        return "Failed to create event"


# ---------------- TEST ENDPOINTS ----------------
@app.post("/test-reminder/")
async def test_reminder(user_input: str):
    """Test reminder creation without WhatsApp"""
    structured = await extract_with_gemini(user_input)
    if not structured:
        return {"error": "Failed to parse input"}

    # Check if complete
    missing = identify_missing_info(structured)
    
    result = {
        "parsed_data": structured,
        "missing_info": missing,
        "is_complete": len(missing) == 0
    }

    if len(missing) == 0 and calendar_service:
        link = create_calendar_event(structured)
        result["calendar_link"] = link
    else:
        result["calendar_link"] = "Calendar not configured or reminder incomplete"

    return result


@app.get("/health/")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "calendar_service": "available" if calendar_service else "not configured",
        "model": MODEL_NAME,
        "timezone": USER_TIMEZONE,
        "active_conversations": len(user_conversations),
        "timestamp": datetime.datetime.now().isoformat()
    }


@app.post("/simulate-message/")
async def simulate_whatsapp_message(text: str, from_number: str = "923141181535"):
    """Simulate a WhatsApp message for testing"""
    logger.info(f"Simulating message: '{text}' from {from_number}")
    
    # Create a mock message structure like WhatsApp would send
    mock_message = {
        "from": from_number,
        "type": "text",
        "text": {"body": text}
    }
    
    mock_contacts = [{
        "wa_id": from_number,
        "profile": {"name": "Test User"}
    }]
    
    await process_incoming_message(mock_message, mock_contacts)
    
    # Return current conversation state
    conversation_state = user_conversations.get(from_number, "No active conversation")
    
    return {
        "status": "message_processed", 
        "text": text, 
        "from": from_number,
        "conversation_state": conversation_state
    }


@app.post("/clear-conversation/")
async def clear_user_conversation(phone_number: str):
    """Clear a user's conversation state"""
    if phone_number in user_conversations:
        del user_conversations[phone_number]
        return {"status": "conversation_cleared", "phone": phone_number}
    else:
        return {"status": "no_active_conversation", "phone": phone_number}


@app.get("/conversations/")
async def get_active_conversations():
    """Get all active conversations"""
    return {
        "active_conversations": len(user_conversations),
        "conversations": {k: v for k, v in user_conversations.items()},
        "management_sessions": len(user_management_state),
        "management_states": {k: v for k, v in user_management_state.items()}
    }


@app.post("/test-list-reminders/")
async def test_list_reminders(date: str = None, phone_number: str = "923141181535"):
    """Test listing reminders for a specific date"""
    if not date:
        date = datetime.datetime.now(pytz.timezone(USER_TIMEZONE)).strftime("%Y-%m-%d")
    
    reminders = get_reminders_for_date(date)
    
    return {
        "date": date,
        "formatted_date": format_date_friendly(date),
        "reminder_count": len(reminders),
        "reminders": [
            {
                "id": r.get("id"),
                "summary": r.get("summary"),
                "start": r.get("start"),
                "formatted_time": format_event_datetime(r)
            } for r in reminders
        ],
        "calendar_service": "available" if calendar_service else "not configured"
    }


@app.post("/test-management-flow/")
async def test_management_flow(text: str, phone_number: str = "923141181535"):
    """Test the reminder management conversation flow"""
    
    # Create mock message structure
    mock_message = {
        "from": phone_number,
        "type": "text",
        "text": {"body": text}
    }
    
    mock_contacts = [{
        "wa_id": phone_number,
        "profile": {"name": "Test User"}
    }]
    
    # Process the message
    await process_incoming_message(mock_message, mock_contacts)
    
    # Return current states
    return {
        "status": "management_flow_processed",
        "text": text,
        "from": phone_number,
        "conversation_state": user_conversations.get(phone_number, "No active conversation"),
        "management_state": user_management_state.get(phone_number, "No management session"),
        "active_conversations": len(user_conversations),
        "active_management_sessions": len(user_management_state)
    }
