# WhatBot - WhatsApp Reminder Management System

## 🚀 Overview

WhatBot is an intelligent WhatsApp-based reminder management system that allows users to create, manage, edit, and delete reminders through natural language conversations. The system integrates with Google Calendar for persistent storage and uses Google's Gemini AI for natural language processing.

## 📋 Table of Contents

1. [System Architecture](#system-architecture)
2. [Core Features](#core-features)
3. [API Endpoints](#api-endpoints)
4. [Configuration](#configuration)
5. [Message Processing Flow](#message-processing-flow)
6. [Reminder Management](#reminder-management)
7. [Calendar Integration](#calendar-integration)
8. [AI Processing](#ai-processing)
9. [Error Handling](#error-handling)
10. [Testing](#testing)
11. [Deployment](#deployment)
12. [Troubleshooting](#troubleshooting)

---

## 🏗️ System Architecture

### Tech Stack
- **Framework**: FastAPI (Python)
- **AI Engine**: Google Gemini 2.0 Flash Exp
- **Calendar**: Google Calendar API v3
- **Messaging**: WhatsApp Business API
- **Authentication**: OAuth2 & Service Account
- **Timezone**: Asia/Karachi (configurable)
- **Storage**: Google Calendar (persistent), In-memory state management

### Key Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   WhatsApp      │────│    WhatBot      │────│  Google         │
│   Business API  │    │    FastAPI      │    │  Calendar API   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                       ┌─────────────────┐
                       │   Gemini AI     │
                       │   NLP Engine    │
                       └─────────────────┘
```

---

## 🌟 Core Features

### 1. Natural Language Reminder Creation
- **Smart Parsing**: Understands natural language inputs like "Remind me to call mom tomorrow at 3pm"
- **Progressive Clarification**: Asks for missing information intelligently
- **Flexible Input**: Supports various date/time formats and recurring patterns

### 2. Comprehensive Reminder Management
- **List Reminders**: View reminders for today, tomorrow, specific dates, or date ranges
- **Edit Reminders**: Modify existing reminders using natural language
- **Delete Reminders**: Remove individual or all reminders
- **Interactive Management**: Numbered selection system for easy interaction

### 3. Smart Date/Time Processing
- **Relative Dates**: "today", "tomorrow", "next week", "next Monday"
- **Specific Dates**: "December 15", "Jan 20", "15th March"
- **Time Formats**: 12-hour (3pm), 24-hour (15:00), natural language (evening)
- **All-day Events**: Support for reminders without specific times

### 4. Recurring Reminders
- **Frequency Options**: Hourly, Daily, Weekly, Monthly, Yearly
- **Smart Recurrence**: Understands "every Monday", "daily", "monthly"

### 5. Professional User Experience
- **Contextual Emojis**: Visual enhancement without overcrowding
- **Clear Messaging**: Professional tone with friendly interaction
- **Error Recovery**: Helpful guidance when commands aren't understood

---

## 🔌 API Endpoints

### Webhook Endpoints

#### `GET /webhook/`
**Purpose**: WhatsApp webhook verification
- **Parameters**: `hub.mode`, `hub.challenge`, `hub.verify_token`
- **Response**: Challenge string for verification

#### `POST /webhook/`
**Purpose**: Receive incoming WhatsApp messages
- **Payload**: WhatsApp webhook data
- **Processing**: Routes to message handler
- **Response**: Success confirmation

### Testing Endpoints

#### `POST /simulate-message/`
**Purpose**: Simulate WhatsApp messages for testing
```json
{
  "text": "Remind me to call mom tomorrow at 3pm",
  "from_number": "923141181535"
}
```

#### `POST /test-reminder/`
**Purpose**: Test reminder parsing without WhatsApp
```json
{
  "user_input": "Doctor appointment next Monday at 2pm"
}
```

#### `POST /test-list-reminders/`
**Purpose**: Test reminder listing functionality
```json
{
  "date": "2025-09-30",
  "phone_number": "923141181535"
}
```

#### `POST /test-management-flow/`
**Purpose**: Test reminder management conversation flow
```json
{
  "text": "list my reminders today",
  "phone_number": "923141181535"
}
```

### Utility Endpoints

#### `GET /health/`
**Purpose**: System health check
- **Response**: Service status, calendar availability, active sessions

#### `POST /send-text/`
**Purpose**: Send WhatsApp messages manually
```json
{
  "to": "923141181535",
  "message": "Hello from WhatBot!"
}
```

#### `GET /conversations/`
**Purpose**: View active conversation states
- **Response**: Current user conversations and management sessions

#### `POST /clear-conversation/`
**Purpose**: Clear user conversation state
```json
{
  "phone_number": "923141181535"
}
```

---

## ⚙️ Configuration

### Environment Variables
```python
# WhatsApp Configuration
WHATSAPP_URL = "https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
ACCESS_TOKEN = "YOUR_WHATSAPP_ACCESS_TOKEN"
VERIFY_TOKEN = "YOUR_WEBHOOK_VERIFY_TOKEN"

# AI Configuration
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
MODEL_NAME = "gemini-2.0-flash-exp"

# Timezone
USER_TIMEZONE = "Asia/Karachi"
```

### Google Calendar Setup
1. **OAuth Setup**: Place `client_secret_*.json` in project root
2. **Service Account**: Alternative with `credentials.json`
3. **Token Management**: Automatic refresh handling

### Required Files
- `client_secret_*.json` (OAuth credentials)
- `credentials.json` (Service Account - optional)
- `token.pickle` (Generated OAuth tokens)

---

## 📨 Message Processing Flow

### 1. Incoming Message Handler
```python
async def process_incoming_message(message: dict, contacts: list)
```

**Flow**:
1. Extract message content and sender info
2. Get contact name from WhatsApp profile
3. Check for reminder management requests
4. Process reminder creation/clarification
5. Send appropriate response

### 2. Reminder Management Detection
```python
async def handle_reminder_management(text_body: str, from_number: str, contact_name: str)
```

**Triggers**:
- List keywords: "list", "show", "my reminders", "reminders for"
- Delete all keywords: "delete all reminders", "clear all reminders"
- Management mode: Active user sessions

### 3. State Management
```python
user_conversations = {}      # Clarification flows
user_management_state = {}   # Management sessions
```

**States**:
- `listing`: Showing numbered reminders
- `action_selected`: Chosen specific reminder
- `editing`: Modifying reminder details

---

## 📅 Reminder Management

### List Reminders
**Command Examples**:
- "List my reminders today"
- "Show reminders for tomorrow"
- "My reminders this week"

**Response Format**:
```
📅 Your Reminders for Today

Hi User 👋, here are your scheduled reminders:

1. Call mom
   ⏰ Monday, September 29 at 3:00 PM

2. Doctor appointment
   ⏰ Monday, September 29 - All-day

🔧 Management Options:
   Reply with a number (1-2) to edit or delete
   Reply 'cancel' to exit management mode

What would you like to do with these reminders?
```

### Edit Reminders
**Command Examples**:
- "Change time to 4pm"
- "Move to tomorrow"
- "Rename to call doctor"
- "Make it daily"

**Processing**:
1. User selects reminder number
2. Chooses "1" for edit
3. Provides edit instruction
4. Gemini AI processes natural language
5. Calendar event updated
6. Confirmation sent

### Delete Reminders
**Individual Deletion**:
1. User selects reminder number
2. Chooses "2" for delete
3. Immediate deletion and confirmation

**Bulk Deletion**:
- Command: "Delete all reminders"
- Confirms count of deleted reminders

---

## 📆 Calendar Integration

### Event Creation
```python
def create_calendar_event(structured: dict)
```

**Event Structure**:
```json
{
  "summary": "Task name at time",
  "start": {
    "dateTime": "2025-09-30T15:00:00",
    "timeZone": "Asia/Karachi"
  },
  "end": {
    "dateTime": "2025-09-30T15:00:00", 
    "timeZone": "Asia/Karachi"
  },
  "recurrence": ["RRULE:FREQ=DAILY"],
  "description": "Notes and additional context"
}
```

### Event Types
- **Timed Events**: Specific date and time
- **All-day Events**: Date only, no specific time
- **Recurring Events**: RRULE patterns for repetition

### Calendar Operations
- **Create**: `calendar_service.events().insert()`
- **Read**: `calendar_service.events().list()`
- **Update**: `calendar_service.events().update()`
- **Delete**: `calendar_service.events().delete()`

---

## 🤖 AI Processing

### Gemini Integration
```python
async def extract_with_gemini(user_input: str, existing_data=None)
```

**Capabilities**:
- Natural language understanding
- Context-aware parsing
- Progressive information extraction
- Edit instruction processing

### Data Structure
```json
{
  "task": "Call mom",
  "date": "2025-09-30",
  "time": "15:00",
  "recurrence": "none",
  "day_of_week": null,
  "notes": null,
  "title": "Call mom"
}
```

### Clarification System
```python
def identify_missing_info(reminder_data)
def generate_clarification_question(missing_info)
```

**Progressive Questions**:
1. **Task**: "❓ What should I remind you about?"
2. **Date**: "📅 When should I set this reminder?"
3. **Time**: "🕐 At what time should I remind you?"

### Edit Processing
```python
async def process_reminder_edit(edit_text: str, original_event: dict)
```

**Understands**:
- Time changes: "change time to 4pm"
- Date changes: "move to tomorrow"
- Title changes: "rename to doctor visit"
- Recurrence: "make it daily"

---

## 🛡️ Error Handling

### Calendar Errors
- **Service Unavailable**: Graceful degradation
- **Event Not Found**: User-friendly error messages
- **Permission Issues**: Clear guidance for resolution

### AI Processing Errors
- **Parse Failures**: Helpful examples and guidance
- **Invalid Dates**: Format correction suggestions
- **Missing Context**: Progressive clarification

### WhatsApp API Errors
- **Rate Limiting**: Automatic retry logic
- **Token Expiry**: Refresh mechanisms
- **Network Issues**: Robust error recovery

### User Experience
```python
# Example error response
error_msg = f"Hi {contact_name} 👋\n\n"
error_msg += "I couldn't understand your reminder request. Let me help you.\n\n"
error_msg += "Try examples like:\n"
error_msg += "   • 'Remind me to call mom tomorrow at 3pm'\n"
# ... more examples
```

---

## 🧪 Testing

### Unit Testing
- **Message Processing**: Simulate various input formats
- **Date Parsing**: Test relative and absolute dates
- **Calendar Operations**: Mock calendar service responses
- **AI Processing**: Validate structured output

### Integration Testing
- **End-to-end Flows**: Complete reminder creation cycles
- **Management Flows**: Test edit/delete operations
- **Error Scenarios**: Validate error handling

### Test Files
- `test_delete_functionality.py`: Deletion workflow testing
- Manual testing via `/simulate-message/` endpoint

### Testing Commands
```bash
# Test reminder parsing
curl -X POST "http://localhost:8000/test-reminder/" \
  -H "Content-Type: application/json" \
  -d '{"user_input": "Remind me to call mom tomorrow at 3pm"}'

# Simulate WhatsApp message
curl -X POST "http://localhost:8000/simulate-message/" \
  -H "Content-Type: application/json" \
  -d '{"text": "list my reminders today", "from_number": "923141181535"}'
```

---

## 🚀 Deployment

### Local Development
```bash
# Install dependencies
pip install fastapi uvicorn google-generativeai google-api-python-client httpx pytz

# Run server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Expose with ngrok
ngrok http 8000
```

### Production Setup
1. **Server**: Deploy FastAPI application
2. **HTTPS**: Required for WhatsApp webhooks
3. **Environment**: Set production environment variables
4. **Monitoring**: Log management and health checks

### WhatsApp Configuration
1. **Webhook URL**: `https://yourdomain.com/webhook/`
2. **Verify Token**: Must match `VERIFY_TOKEN`
3. **Subscription**: Messages and message_status events

---

## 🔧 Function Reference

### Core Processing Functions

#### `process_incoming_message(message: dict, contacts: list)`
- **Purpose**: Main message processing entry point
- **Parameters**: WhatsApp message object and contact list
- **Returns**: None (async)
- **Flow**: Determines message type and routes to appropriate handler

#### `handle_reminder_management(text_body: str, from_number: str, contact_name: str)`
- **Purpose**: Detect and handle reminder management requests
- **Parameters**: Message text, sender number, contact name
- **Returns**: Boolean indicating if request was handled
- **Features**: Keyword detection, state management, delegation

#### `handle_management_action(text_body: str, from_number: str, contact_name: str, management_state: dict)`
- **Purpose**: Process actions within management flow
- **Parameters**: Message text, sender info, current state
- **Returns**: Boolean
- **Modes**: listing, action_selected, editing

### AI Processing Functions

#### `extract_with_gemini(user_input: str, existing_data=None)`
- **Purpose**: Parse natural language into structured reminder data
- **Parameters**: User input text, optional existing context
- **Returns**: Structured dictionary or None
- **Features**: Context awareness, validation, error handling

#### `process_reminder_edit(edit_text: str, original_event: dict)`
- **Purpose**: Process edit instructions using AI
- **Parameters**: Edit instruction, original event data
- **Returns**: Updated event fields or None
- **Capabilities**: Natural language edit understanding

### Calendar Functions

#### `create_calendar_event(structured: dict)`
- **Purpose**: Create Google Calendar event from structured data
- **Parameters**: Reminder data dictionary
- **Returns**: Event link or error message
- **Features**: Timezone handling, recurrence support

#### `get_reminders_for_date(date_str: str)`
- **Purpose**: Retrieve reminders for specific date
- **Parameters**: Date in YYYY-MM-DD format
- **Returns**: List of calendar events
- **Features**: Date range queries, filtering

#### `delete_calendar_event(event_id: str)`
- **Purpose**: Delete calendar event by ID
- **Parameters**: Google Calendar event ID
- **Returns**: Boolean success status
- **Features**: Existence validation, error handling

#### `update_calendar_event(event_id: str, updates: dict)`
- **Purpose**: Update existing calendar event
- **Parameters**: Event ID and update fields
- **Returns**: Boolean success status
- **Features**: Partial updates, validation

### Utility Functions

#### `parse_date_from_text(text: str)`
- **Purpose**: Extract dates from natural language
- **Parameters**: Text containing date references
- **Returns**: Date string in YYYY-MM-DD format or None
- **Supports**: Relative dates, specific dates, month names

#### `format_date_friendly(date_str: str)`
- **Purpose**: Convert dates to human-readable format
- **Parameters**: Date in YYYY-MM-DD format
- **Returns**: Friendly date string
- **Examples**: "Today", "Tomorrow", "Monday, September 29, 2025"

#### `format_event_datetime(event: dict)`
- **Purpose**: Format calendar event datetime for display
- **Parameters**: Google Calendar event object
- **Returns**: Formatted datetime string
- **Features**: Timezone conversion, all-day detection

#### `identify_missing_info(reminder_data)`
- **Purpose**: Identify incomplete reminder fields
- **Parameters**: Structured reminder data
- **Returns**: List of missing field names
- **Logic**: Smart validation based on reminder type

#### `generate_clarification_question(missing_info)`
- **Purpose**: Generate helpful clarification questions
- **Parameters**: List of missing information
- **Returns**: Question string with examples
- **Features**: Progressive questioning, contextual examples

---

## 🔍 Troubleshooting

### Common Issues

#### Calendar Not Working
**Symptoms**: "Calendar not configured" messages
**Solutions**:
1. Check credentials files exist
2. Verify OAuth token validity
3. Run `python setup_calendar.py`
4. Check Google Calendar API enablement

#### WhatsApp Messages Not Received
**Symptoms**: No webhook calls
**Solutions**:
1. Verify webhook URL accessibility
2. Check HTTPS certificate
3. Confirm webhook subscription
4. Validate verify token

#### AI Parsing Failures
**Symptoms**: "Couldn't understand" responses
**Solutions**:
1. Check Gemini API key
2. Verify model availability
3. Review prompt structure
4. Test with simpler inputs

#### Memory State Issues
**Symptoms**: Lost conversation context
**Solutions**:
1. Check user_conversations dict
2. Clear stuck states via API
3. Restart service for cleanup
4. Implement persistent storage

### Debug Endpoints

#### Health Check
```bash
curl http://localhost:8000/health/
```

#### Active Conversations
```bash
curl http://localhost:8000/conversations/
```

#### Clear User State
```bash
curl -X POST "http://localhost:8000/clear-conversation/" \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "923141181535"}'
```

### Logging
- **Level**: INFO (configurable)
- **Location**: Console output
- **Content**: Message processing, API calls, errors
- **Format**: Structured logging with timestamps

---

## 📈 Performance Considerations

### Scalability
- **State Management**: In-memory (consider Redis for production)
- **API Rate Limits**: WhatsApp Business API restrictions
- **Calendar Quotas**: Google Calendar API limits
- **AI Processing**: Gemini API rate limits

### Optimization
- **Caching**: Calendar events for frequently accessed dates
- **Batching**: Multiple calendar operations
- **Connection Pooling**: HTTP client reuse
- **Response Times**: Async processing for better UX

### Monitoring
- **Health Checks**: Regular service status verification
- **Error Tracking**: Comprehensive error logging
- **Usage Metrics**: Conversation and reminder statistics
- **Performance Metrics**: Response times and throughput

---

## 🔮 Future Enhancements

### Planned Features
1. **Multiple Timezone Support**: Per-user timezone preferences
2. **Rich Media**: Image and voice message support
3. **Reminder Templates**: Quick reminder creation
4. **Group Reminders**: Shared reminders for groups
5. **Advanced Recurrence**: Complex recurring patterns
6. **Integration Extensions**: Task management, email notifications

### Technical Improvements
1. **Persistent State**: Database-backed conversation state
2. **Webhooks Security**: Enhanced validation and authentication
3. **API Versioning**: Structured version management
4. **Microservices**: Separate AI and calendar services
5. **Real-time Notifications**: WebSocket support for instant updates

---

## 📝 Conclusion

WhatBot provides a comprehensive, intelligent reminder management solution through WhatsApp, combining natural language processing with robust calendar integration. The system is designed for reliability, scalability, and ease of use, making reminder management as simple as having a conversation.

The modular architecture allows for easy extension and maintenance, while the comprehensive API provides flexibility for testing and integration. With proper deployment and configuration, WhatBot can serve as a powerful personal assistant for reminder management.

For additional support or contributions, please refer to the project repository and documentation updates.

---

**Version**: 1.0  
**Last Updated**: September 29, 2025  
**Author**: WhatBot Development Team  
**License**: Proprietary