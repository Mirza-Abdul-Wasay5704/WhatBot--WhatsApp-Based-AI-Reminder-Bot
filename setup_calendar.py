"""
Enhanced OAuth Setup for Google Calendar with Multi-Account Support
Run this when your main server is NOT running
"""

import os
import pickle
import webbrowser
import glob
import shutil
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/calendar']

# Get OAuth credentials file from environment or use default
CLIENT_FILE = os.getenv("GOOGLE_OAUTH_CREDENTIALS_FILE", 
                       'client_secret_428819923956-is6irhla4qp3phl2ij7ik2vv9cpecd4p.apps.googleusercontent.com.json')

# Get token pickle file from environment or use default
TOKEN_PICKLE_FILE = os.getenv("GOOGLE_TOKEN_PICKLE_FILE", "token.pickle")

def get_calendar_info(creds):
    """Get calendar information to identify the account"""
    try:
        service = build('calendar', 'v3', credentials=creds)
        
        # Get primary calendar info
        calendar = service.calendars().get(calendarId='primary').execute()
        email = calendar.get('id', 'Unknown')
        summary = calendar.get('summary', 'Unknown')
        
        # Get calendar list to find more info
        calendar_list = service.calendarList().list().execute()
        primary_cal = None
        for cal in calendar_list.get('items', []):
            if cal.get('primary', False):
                primary_cal = cal
                break
        
        if primary_cal:
            email = primary_cal.get('id', email)
            summary = primary_cal.get('summaryOverride') or primary_cal.get('summary', summary)
        
        return {
            'email': email,
            'name': summary,
            'success': True
        }
    except Exception as e:
        return {
            'email': 'Unknown',
            'name': 'Cannot access',
            'success': False,
            'error': str(e)
        }

def get_account_info(pickle_file):
    """Try to get detailed account info from pickle file"""
    try:
        with open(pickle_file, 'rb') as token:
            creds = pickle.load(token)
        
        # Check if credentials are valid
        if creds and creds.valid:
            status = "✅ Valid"
            # Try to get calendar info for valid credentials
            cal_info = get_calendar_info(creds)
            if cal_info['success']:
                identifier = cal_info['email']
                display_name = cal_info['name'] if cal_info['name'] != cal_info['email'] else cal_info['email']
            else:
                identifier = "Valid account"
                display_name = "Valid but cannot access calendar"
        elif creds and creds.expired:
            status = "⚠️  Expired"
            # For expired creds, try to get basic info without API call
            identifier = "Expired account"
            display_name = "Expired credentials"
            
            # Try to refresh and get info if possible
            if creds.refresh_token:
                try:
                    temp_creds = Credentials(
                        token=creds.token,
                        refresh_token=creds.refresh_token,
                        token_uri=creds.token_uri,
                        client_id=creds.client_id,
                        client_secret=creds.client_secret
                    )
                    temp_creds.refresh(GoogleRequest())
                    cal_info = get_calendar_info(temp_creds)
                    if cal_info['success']:
                        identifier = cal_info['email']
                        display_name = f"{cal_info['name']} (Expired)"
                except:
                    pass
        else:
            status = "❌ Invalid"
            identifier = "Cannot read credentials"
            display_name = "Invalid file"
        
        return {
            'status': status,
            'identifier': identifier,
            'display_name': display_name,
            'valid': creds and creds.valid if creds else False
        }
    except Exception as e:
        return {
            'status': f"❌ Error: {str(e)[:20]}...",
            'identifier': "Cannot read file",
            'display_name': f"Error: {str(e)[:30]}...",
            'valid': False
        }

def suggest_filename_from_credentials(creds):
    """Suggest a filename based on credential information"""
    try:
        if creds and creds.valid:
            cal_info = get_calendar_info(creds)
            if cal_info['success']:
                email = cal_info['email']
                # Extract username from email
                username = email.split('@')[0] if '@' in email else email
                # Clean username for filename
                clean_name = "".join(c for c in username if c.isalnum() or c in "._-").lower()
                return f"token_{clean_name}.pickle"
        
        # Fallback to timestamp if no email available
        import time
        timestamp = str(int(time.time()))[-6:]  # Last 6 digits of timestamp
        return f"token_account_{timestamp}.pickle"
    except:
        import time
        timestamp = str(int(time.time()))[-6:]
        return f"token_new_{timestamp}.pickle"

def find_pickle_files():
    """Find all .pickle files in the current directory"""
    pickle_files = glob.glob("*.pickle")
    return sorted(pickle_files)

def display_pickle_files(pickle_files):
    """Display available pickle files with their account information"""
    print("📁 Available Google Account Credentials:")
    print()
    
    for i, pickle_file in enumerate(pickle_files, 1):
        info = get_account_info(pickle_file)
        active_marker = " 🟢 (ACTIVE)" if pickle_file == TOKEN_PICKLE_FILE else ""
        print(f"   {i} - {pickle_file}{active_marker}")
        print(f"       Status: {info['status']}")
        print(f"       Account: {info['display_name']}")
        print(f"       Email: {info['identifier']}")
        print()
    
    print(f"   {len(pickle_files) + 1} - Create new account setup")
    print()

def copy_to_token_pickle(source_file):
    """Copy the credentials from selected file to the configured token file"""
    try:
        if source_file == TOKEN_PICKLE_FILE:
            print(f"✅ Already using {TOKEN_PICKLE_FILE}")
            return True
        
        # Load credentials from source file
        with open(source_file, 'rb') as source:
            creds = pickle.load(source)
        
        # Save credentials to target file (overwrite if exists)
        with open(TOKEN_PICKLE_FILE, 'wb') as target:
            pickle.dump(creds, target)
        
        print(f"✅ Copied credentials from {source_file} to {TOKEN_PICKLE_FILE}")
        print("✅ Your main.py will now use this account automatically")
        return True
        
    except Exception as e:
        print(f"❌ Error copying credentials: {e}")
        return False

def select_pickle_file(pickle_files):
    """Let user select from existing pickle files or create new"""
    while True:
        try:
            choice = input(f"Enter your choice (1-{len(pickle_files) + 1}): ").strip()
            choice_num = int(choice)
            
            if 1 <= choice_num <= len(pickle_files):
                selected_file = pickle_files[choice_num - 1]
                print(f"📄 Selected: {selected_file}")
                return selected_file
            elif choice_num == len(pickle_files) + 1:
                return "NEW_ACCOUNT"
            else:
                print(f"❌ Please enter a number between 1 and {len(pickle_files) + 1}")
        except ValueError:
            print("❌ Please enter a valid number")

def create_new_pickle_name(creds=None):
    """Create a new pickle file name automatically using credential email"""
    print()
    print("📝 Creating new account setup...")
    
    # Automatically name using credentials if available
    if creds:
        suggested_name = suggest_filename_from_credentials(creds)
        if suggested_name:
            print(f"� Auto-naming file: {suggested_name}")
            return suggested_name
    
    # Fallback to timestamp-based naming
    import time
    timestamp = str(int(time.time()))[-6:]
    pickle_name = f"token_account_{timestamp}.pickle"
    print(f"💾 Auto-naming file: {pickle_name}")
    return pickle_name

def main():
    print("🔧 Google Calendar OAuth Setup")
    print("⚠️  IMPORTANT: Stop your main server (uvicorn) before running this!")
    print()
    
    # Check if uvicorn is running on port 8000
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', 8000))
        sock.close()
        
        if result == 0:
            print("❌ ERROR: Server is running on port 8000!")
            print("❌ Please stop uvicorn first (press Ctrl+C in the server terminal)")
            print("❌ Then run this script again")
            return False
    except Exception:
        pass  # Port check failed, but we can continue
    
    # Find all existing pickle files
    pickle_files = find_pickle_files()
    
    print("🔍 Scanning for existing Google account credentials...")
    print()
    
    if pickle_files:
        print(f"📋 Found {len(pickle_files)} existing credential file(s)")
        display_pickle_files(pickle_files)
        
        # Let user select existing or create new
        selected = select_pickle_file(pickle_files)
        
        if selected == "NEW_ACCOUNT":
            # Create new account
            pickle_file = create_new_pickle_name()
            print(f"🆕 Will create new account: {pickle_file}")
            creds = None
            setup_new = True
        else:
            # Use existing pickle file
            pickle_file = selected
            try:
                with open(pickle_file, 'rb') as token:
                    creds = pickle.load(token)
                print(f"📄 Loaded credentials from: {pickle_file}")
                setup_new = False
            except Exception as e:
                print(f"❌ Error loading {pickle_file}: {e}")
                return False
    else:
        print("📋 No existing credential files found")
        print("🆕 Will create new account setup")
        pickle_file = TOKEN_PICKLE_FILE  # Default name for first setup
        creds = None
        setup_new = True
    
    # Handle existing credentials
    if not setup_new and creds:
        info = get_account_info(pickle_file)
        print()
        print(f"📊 Account Status: {info['status']}")
        print(f"📧 Account: {info['display_name']}")
        
        if creds.valid:
            print("✅ Current credentials are valid and active")
            print()
            print("🔧 Options:")
            print(f"   1 - Use this account (copy to {TOKEN_PICKLE_FILE})")
            print("   2 - Refresh this account (re-authenticate)")
            print("   3 - Go back to account selection")
            print()
            
            while True:
                choice = input("Enter your choice (1, 2, or 3): ").strip()
                if choice in ['1', '2', '3']:
                    break
                print("❌ Please enter 1, 2, or 3")
            
            if choice == '1':
                print("✅ Using existing account")
                
                # Copy selected file to token.pickle for main.py
                if copy_to_token_pickle(pickle_file):
                    print()
                    print("🚀 Start your WhatsApp bot:")
                    print("   uvicorn main:app --reload")
                    return True
                else:
                    return False
            elif choice == '2':
                print("🔄 Will refresh this account...")
                creds = None  # Force new auth
            elif choice == '3':
                print("↩️  Returning to account selection...")
                return main()  # Restart the process
        else:
            print("⚠️  Credentials are invalid or expired")
            print()
            print("🔧 Options:")
            print("   1 - Try to refresh this account")
            print("   2 - Replace with new authentication")
            print("   3 - Go back to account selection")
            print()
            
            while True:
                choice = input("Enter your choice (1, 2, or 3): ").strip()
                if choice in ['1', '2', '3']:
                    break
                print("❌ Please enter 1, 2, or 3")
            
            if choice == '2':
                print("🔄 Will replace with new authentication...")
                creds = None
            elif choice == '3':
                print("↩️  Returning to account selection...")
                return main()  # Restart the process
    
    # If there are no valid credentials, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("🔄 Attempting to refresh expired credentials...")
                creds.refresh(GoogleRequest())
                print("✅ Credentials refreshed successfully")
            except Exception as e:
                print(f"❌ Failed to refresh: {e}")
                print("🔄 Will proceed with new authentication...")
                creds = None
        
        if not creds:
            if not os.path.exists(CLIENT_FILE):
                print(f"❌ Client secrets file not found: {CLIENT_FILE}")
                print("💡 Please ensure you have downloaded the OAuth credentials from Google Cloud Console")
                return False
            
            print()
            print("🌐 Starting Google OAuth authentication...")
            print("📱 This will open your browser for Google login")
            print("🔐 Please sign in with the Google account you want to use for calendar access")
            print()
            input("Press Enter to continue...")
            
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_FILE, SCOPES)
            
            # Use port 8000 to match the redirect URI in your credentials
            try:
                creds = flow.run_local_server(port=8000, open_browser=True)
                print("✅ OAuth authentication completed successfully!")
                
                # If this is a new account, suggest filename based on credentials
                if setup_new and pickle_file != TOKEN_PICKLE_FILE:
                    suggested_file = suggest_filename_from_credentials(creds)
                    if suggested_file and suggested_file != pickle_file:
                        print(f"💡 Based on your account, suggested filename: {suggested_file}")
                        use_suggested = input("Use suggested filename instead? (y/n): ").strip().lower()
                        if use_suggested in ['y', 'yes']:
                            pickle_file = suggested_file
            except Exception as e:
                print(f"❌ OAuth failed: {e}")
                print("💡 Troubleshooting tips:")
                print("   - Check your internet connection")
                print("   - Verify Google credentials file is correct")
                print("   - Ensure port 8000 is not blocked by firewall")
                print("   - Try running the script as administrator")
                return False
        
        # Save the credentials
        try:
            with open(pickle_file, 'wb') as token:
                pickle.dump(creds, token)
            print(f"💾 Credentials saved to {pickle_file}")
            
            # Get and display account info
            try:
                cal_info = get_calendar_info(creds)
                if cal_info['success']:
                    print(f"📧 Account: {cal_info['name']}")
                    print(f"📨 Email: {cal_info['email']}")
            except:
                print("📧 Account successfully configured for calendar access")
                
        except Exception as e:
            print(f"❌ Failed to save credentials: {e}")
            return False
        
        # Copy to configured token file if it's not already
        if pickle_file != TOKEN_PICKLE_FILE:
            if copy_to_token_pickle(pickle_file):
                print()
            else:
                return False
    
    else:
        print("✅ Valid credentials confirmed")
        # Copy to configured token file for main.py
        if copy_to_token_pickle(pickle_file):
            print()
        else:
            return False
    
    print()
    print("🎉 Google Calendar setup complete!")
    print("✅ Your WhatsApp bot now has calendar access")
    print()
    print("🚀 Start your bot with:")
    print("   uvicorn main:app --reload")
    print()
    print("💡 Tips:")
    print("   - Test with: 'Remind me to call mom tomorrow at 3pm'")
    print("   - List reminders: 'Show my reminders today'")
    print("   - Manage reminders: Select numbers to edit/delete")
    print()
    print(f"📁 Active credential file: {pickle_file}")
    
    return True

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ Setup cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        print("💡 Please check your internet connection and Google credentials")