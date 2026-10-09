#!/usr/bin/env python3
"""
CorrigoPro Automation Agent
Checks completed work orders from app and submits to CorrigoPro web portal.
Runs every 15 minutes.
"""
import json
import os
import time
from datetime import datetime
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

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

def setup_webdriver():
    """Setup Chrome WebDriver in headless mode."""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')

    driver = webdriver.Chrome(options=chrome_options)
    return driver

def login_to_corrigo(driver):
    """Log into CorrigoPro web portal."""
    try:
        log("🔐 Logging into CorrigoPro...")
        driver.get(CORRIGO_URL)

        # Wait for username field
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )

        # Enter credentials
        driver.find_element(By.NAME, "username").send_keys(CORRIGO_USERNAME)
        driver.find_element(By.NAME, "password").send_keys(CORRIGO_PASSWORD)

        # Click login
        driver.find_element(By.XPATH, "//button[contains(text(), 'Log In') or contains(@type, 'submit')]").click()

        # Wait for dashboard
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        time.sleep(2)
        log("✅ Successfully logged into CorrigoPro")
        return True
    except TimeoutException:
        log("⚠️ Login timeout - check credentials or page structure")
        return False
    except Exception as e:
        log(f"❌ Login error: {e}")
        return False

def find_work_order(driver, wo_number):
    """Find a work order by number in CorrigoPro."""
    try:
        # Look for search box
        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//input[contains(@placeholder, 'search') or contains(@placeholder, 'Search') or @name='search']"))
        )
        search_box.clear()
        search_box.send_keys(wo_number)

        # Click search button
        search_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Search') or contains(@type, 'submit')]")
        search_btn.click()

        time.sleep(3)

        # Look for work order in results
        wo_elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{wo_number}')]")
        if wo_elements:
            return wo_elements[0]
        return None
    except TimeoutException:
        log(f"⚠️ Could not find search box for work order {wo_number}")
        return None
    except Exception as e:
        log(f"❌ Error finding work order {wo_number}: {e}")
        return None

def submit_action(driver, action, bid_amount=None):
    """Submit accept/decline/bid action for current work order."""
    try:
        if action == 'accept':
            # Find and click Accept button
            accept_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'ACCEPT')]"))
            )
            accept_btn.click()
            log(f"✅ Clicked Accept")

        elif action == 'decline':
            # Find and click Decline button
            decline_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Decline') or contains(text(), 'DECLINE')]"))
            )
            decline_btn.click()
            log(f"✅ Clicked Decline")

        elif action == 'bid':
            # Find bid input and submit
            bid_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@type='number' or contains(@name, 'bid') or contains(@placeholder, 'bid')]"))
            )
            bid_input.clear()
            bid_input.send_keys(str(bid_amount))

            # Click submit bid
            submit_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Submit') or contains(text(), 'Submit Bid')]")
            submit_btn.click()
            log(f"✅ Submitted bid of ${bid_amount}")

        # Wait for confirmation
        time.sleep(2)
        return True

    except TimeoutException:
        log(f"⚠️ Could not find {action} button or input")
        return False
    except Exception as e:
        log(f"❌ Error submitting {action}: {e}")
        return False

def process_pending_actions(actions_list):
    """Process all pending actions and submit to CorrigoPro."""
    if not actions_list:
        log("ℹ️ No pending actions to process")
        return []

    log(f"🚀 Processing {len(actions_list)} pending actions...")

    # Setup webdriver
    driver = setup_webdriver()
    processed_ids = []

    try:
        # Login
        if not login_to_corrigo(driver):
            log("❌ Failed to login, aborting")
            return processed_ids

        # Process each action
        for action in actions_list:
            action_id = action['id']
            wo_number = action['number']
            action_type = action['action']
            bid_amount = action.get('bidAmount')

            log(f"📋 Processing {wo_number} - Action: {action_type}")

            # Find work order
            wo_element = find_work_order(driver, wo_number)
            if not wo_element:
                log(f"⚠️ Could not find work order {wo_number}, skipping")
                continue

            # Submit action
            if submit_action(driver, action_type, bid_amount):
                processed_ids.append(action_id)
                log(f"✅ Successfully processed {wo_number}")
            else:
                log(f"❌ Failed to process {wo_number}")

            # Small delay between actions
            time.sleep(2)

    except Exception as e:
        log(f"❌ Error during processing: {e}")
    finally:
        driver.quit()

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
