#!/usr/bin/env python3
"""
CorrigoPro Automation - HTTP-based (no browser required)
Submits Gary's accept/decline/bid actions to CorrigoPro.
"""
import json
import os
import time
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# Configuration
CORRIGO_URL = "https://login.corrigo.com"
ACTIONS_FILE = "corrigo-actions.json"
WORK_ORDERS_FILE = "work-orders.json"
GITHUB_REPO = "Simzy420/big-brain-ape-dashboard"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
CORRIGO_USERNAME = os.environ.get("CORRIGO_USERNAME")
CORRIGO_PASSWORD = os.environ.get("CORRIGO_PASSWORD")

# Log file
LOG_FILE = "/workspace/corrigo_automation.log"

def log(message):
    """Write to log file with timestamp."""
    timestamp = datetime.now().isoformat()
    log_entry = f"[{timestamp}] {message}\n"
    with open(LOG_FILE, 'a') as f:
        f.write(log_entry)
    print(log_entry.strip())

def load_pending_actions():
    """Load pending actions from GitHub."""
    try:
        response = requests.get(
            f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{ACTIONS_FILE}",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            log(f"✅ Loaded {data.get('count', 0)} pending actions")
            return data.get('pendingActions', [])
        else:
            log(f"⚠️ Failed to load pending actions: {response.status_code}")
            return []
    except Exception as e:
        log(f"❌ Error loading pending actions: {e}")
        return []

def mark_actions_submitted(processed_ids):
    """Mark actions as submitted by updating work-orders.json on GitHub."""
    try:
        # Load work orders
        response = requests.get(
            f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{WORK_ORDERS_FILE}",
            timeout=10
        )
        if response.status_code != 200:
            log(f"⚠️ Failed to load work-orders.json: {response.status_code}")
            return

        work_orders = response.json()

        # Mark processed IDs as submitted
        updated_count = 0
        for wo in work_orders:
            if wo.get('id') in processed_ids and not wo.get('corrigoSubmitted'):
                wo['corrigoSubmitted'] = True
                wo['corrigoSubmittedAt'] = datetime.now().isoformat()
                updated_count += 1

        if updated_count > 0:
            # Update work-orders.json on GitHub
            url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{WORK_ORDERS_FILE}"
            headers = {
                'Authorization': f'token {GITHUB_TOKEN}',
                'Content-Type': 'application/json'
            }

            # Get current SHA
            response = requests.get(url, headers=headers)
            sha = response.json().get('sha') if response.status_code == 200 else None

            # Update file
            data = {
                'message': f'Marked {updated_count} actions as submitted to CorrigoPro',
                'content': json.dumps(work_orders, indent=2),
            }
            if sha:
                data['sha'] = sha

            response = requests.put(url, headers=headers, json=data)
            if response.status_code in [200, 201]:
                log(f"✅ Marked {updated_count} actions as submitted")
            else:
                log(f"⚠️ Failed to update work-orders.json: {response.status_code}")

    except Exception as e:
        log(f"❌ Error marking actions as submitted: {e}")

def login_to_corrigo():
    """Login to CorrigoPro using HTTP requests."""
    try:
        log("🔐 Logging into CorrigoPro...")
        
        # Start a session
        session = requests.Session()
        
        # GET login page to get any CSRF tokens
        login_page = session.get(CORRIGO_URL, timeout=10)
        log(f"✅ Got login page (status: {login_page.status_code})")
        
        # Parse login page to find form fields
        soup = BeautifulSoup(login_page.text, 'html.parser')
        
        # Find login form
        login_form = soup.find('form')
        if not login_form:
            # Try to find any input fields
            form_data = {}
        else:
            # Extract all hidden fields
            form_data = {}
            for input_tag in login_form.find_all('input', type='hidden'):
                if input_tag.get('name') and input_tag.get('value'):
                    form_data[input_tag['name']] = input_tag['value']
        
        # Add credentials
        form_data['username'] = CORRIGO_USERNAME
        form_data['password'] = CORRIGO_PASSWORD
        
        # POST login
        login_response = session.post(
            CORRIGO_URL,
            data=form_data,
            allow_redirects=True,
            timeout=10
        )
        log(f"✅ Posted login (status: {login_response.status_code})")
        
        # Check if login succeeded
        if 'error' in login_response.text.lower() or 'invalid' in login_response.text.lower():
            log("❌ Login failed - credentials may be incorrect")
            return None
        
        # Check for redirect to dashboard
        if 'dashboard' in login_response.url.lower() or login_response.status_code in [200, 302]:
            log("✅ Successfully logged into CorrigoPro")
            return session
        else:
            log(f"⚠️ Login response URL: {login_response.url}")
            return session  # Return session anyway to try next steps
            
    except Exception as e:
        log(f"❌ Login error: {e}")
        return None

def find_work_order(session, wo_number):
    """Find a work order by number in CorrigoPro."""
    try:
        log(f"🔍 Searching for work order {wo_number}...")
        
        # Try to navigate to work order list or search
        search_url = f"{CORRIGO_URL}/search"
        search_response = session.get(search_url, timeout=10)
        
        # Parse page to find work order link
        soup = BeautifulSoup(search_response.text, 'html.parser')
        
        # Look for links containing the work order number
        wo_link = None
        for a in soup.find_all('a', href=True):
            if wo_number in a.text or wo_number in a.get('href', ''):
                wo_link = a.get('href')
                break
        
        if wo_link:
            log(f"✅ Found work order link: {wo_link}")
            return wo_link
        else:
            log(f"⚠️ Could not find work order {wo_number}")
            return None
            
    except Exception as e:
        log(f"❌ Error finding work order: {e}")
        return None

def submit_action(session, wo_url, action, bid_amount=None):
    """Submit accept/decline/bid action for current work order."""
    try:
        log(f"📋 Submitting action: {action}")
        
        # Navigate to work order page
        wo_page = session.get(wo_url, timeout=10)
        soup = BeautifulSoup(wo_page.text, 'html.parser')
        
        # Find form with action buttons
        form = soup.find('form')
        if not form:
            log("⚠️ Could not find action form")
            return False
        
        # Extract form data
        form_data = {}
        for input_tag in form.find_all('input', type='hidden'):
            if input_tag.get('name') and input_tag.get('value'):
                form_data[input_tag['name']] = input_tag['value']
        
        # Add action parameter
        if action == 'accept':
            form_data['action'] = 'accept'
        elif action == 'decline':
            form_data['action'] = 'decline'
        elif action == 'bid':
            form_data['action'] = 'bid'
            if bid_amount:
                form_data['bidAmount'] = bid_amount
        
        # Submit the form
        form_action = form.get('action', wo_url)
        submit_response = session.post(form_action, data=form_data, timeout=10)
        
        # Check for success
        if submit_response.status_code == 200:
            log(f"✅ Successfully submitted {action}")
            return True
        else:
            log(f"⚠️ Submit response status: {submit_response.status_code}")
            return False
            
    except Exception as e:
        log(f"❌ Error submitting action: {e}")
        return False

def process_pending_actions(actions_list):
    """Process all pending actions and submit to CorrigoPro."""
    if not actions_list:
        log("ℹ️ No pending actions to process")
        return []

    log(f"🚀 Processing {len(actions_list)} pending actions...")

    # Login
    session = login_to_corrigo()
    if not session:
        log("❌ Failed to login, aborting")
        return []

    processed_ids = []

    try:
        # Process each action
        for action in actions_list:
            action_id = action['id']
            wo_number = action['number']
            action_type = action['action']
            bid_amount = action.get('bidAmount')

            log(f"📋 Processing {wo_number} - Action: {action_type}")

            # Find work order
            wo_url = find_work_order(session, wo_number)
            if not wo_url:
                log(f"⚠️ Could not find work order {wo_number}, skipping")
                continue

            # Submit action
            if submit_action(session, wo_url, action_type, bid_amount):
                processed_ids.append(action_id)
                log(f"✅ Successfully processed {wo_number}")
            else:
                log(f"❌ Failed to process {wo_number}")

            # Small delay between actions
            time.sleep(2)

    except Exception as e:
        log(f"❌ Error during processing: {e}")
    finally:
        log("🚪 Closing session")
        # No explicit close needed for requests.Session

    return processed_ids

def main():
    """Main execution."""
    log("=" * 50)
    log("Starting CorrigoPro automation cycle")
    log("=" * 50)

    # Load pending actions
    pending = load_pending_actions()

    if not pending:
        log("ℹ️ No pending actions found")
        return

    # Process actions
    processed_ids = process_pending_actions(pending)

    if processed_ids:
        log(f"✅ Successfully processed {len(processed_ids)} actions")
        # Mark as submitted
        mark_actions_submitted(processed_ids)
    else:
        log("ℹ️ No actions were processed")

    log("=" * 50)
    log("CorrigoPro automation cycle complete")
    log("=" * 50)

if __name__ == '__main__':
    main()