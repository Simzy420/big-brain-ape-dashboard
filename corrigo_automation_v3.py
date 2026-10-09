#!/usr/bin/env python3
"""
CorrigoPro Automation - Playwright-based
Reads Gary's accept/decline/bid actions from GitHub and submits them on CorrigoPro.
"""
import asyncio
import json
import os
from datetime import datetime
from playwright.async_api import async_playwright
import requests

# Configuration
CORRIGO_USERNAME = os.environ.get("CORRIGO_USERNAME", "")
CORRIGO_PASSWORD = os.environ.get("CORRIGO_PASSWORD", "")
CORRIGO_URL = "https://am-desktop.corrigopro.com/"
ACTIONS_FILE = "corrigo-actions.json"
WORK_ORDERS_FILE = "work-orders.json"
GITHUB_REPO = "Simzy420/big-brain-ape-dashboard"

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", os.environ.get("GITHUB_TOKEN_SIMZY", ""))

LOG_FILE = "/workspace/corrigo_automation.log"

def log(message):
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
            actions = data.get('pendingActions', [])
            log(f"✅ Loaded {len(actions)} pending actions")
            return actions
        else:
            log(f"⚠️ No actions file (status: {response.status_code})")
            return []
    except Exception as e:
        log(f"❌ Error loading pending actions: {e}")
        return []

def mark_actions_submitted(processed_ids):
    """Mark actions as submitted by clearing them from corrigo-actions.json on GitHub."""
    if not processed_ids:
        return
    
    try:
        # Just clear the processed ones from the file
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{ACTIONS_FILE}"
        headers = {
            'Authorization': f'token {GITHUB_TOKEN}',
            'Content-Type': 'application/json'
        }

        # Get current file SHA
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            log(f"⚠️ Could not get file SHA: {response.status_code}")
            return
        
        sha = response.json().get('sha')
        
        # Load current actions
        actions_data = requests.get(
            f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{ACTIONS_FILE}",
            timeout=10
        ).json()
        
        # Remove processed actions
        remaining = [a for a in actions_data.get('pendingActions', []) if a['id'] not in processed_ids]
        
        export_data = {
            'pendingActions': remaining,
            'exportedAt': datetime.now().isoformat(),
            'count': len(remaining)
        }
        
        import base64
        data = {
            'message': f'Processed {len(processed_ids)} actions on CorrigoPro',
            'content': base64.b64encode(json.dumps(export_data, indent=2).encode()).decode(),
        }
        if sha:
            data['sha'] = sha

        response = requests.put(url, headers=headers, json=data, timeout=10)
        if response.status_code in [200, 201]:
            log(f"✅ Cleared {len(processed_ids)} processed actions")
        else:
            log(f"⚠️ Failed to update actions file: {response.status_code}")

    except Exception as e:
        log(f"❌ Error marking actions submitted: {e}")

async def login_to_corrigo(page):
    """Login to CorrigoPro."""
    try:
        log("🔐 Logging into CorrigoPro...")
        
        # Wait for login form
        await page.wait_for_selector('input[name="UserName"]', timeout=10000)
        await page.fill('input[name="UserName"]', CORRIGO_USERNAME)
        await page.fill('input[name="Password"]', CORRIGO_PASSWORD)
        await page.click('input[type="submit"]')
        await page.wait_for_load_state('domcontentloaded', timeout=30000)
        await asyncio.sleep(5)
        
        if 'login' not in page.url.lower():
            log("✅ Logged in successfully")
            return True
        else:
            log("❌ Login failed")
            return False
            
    except Exception as e:
        log(f"❌ Login error: {e}")
        return False

async def process_action(page, action):
    """Process a single action - find work order and click the button."""
    wo_number = action['number']
    action_type = action['action']
    bid_amount = action.get('bidAmount')
    
    log(f"📋 Processing {wo_number} - Action: {action_type}")
    
    try:
        # Search for the work order
        search_box = await page.wait_for_selector('#header-search', timeout=10000)
        await search_box.fill('')
        await search_box.fill(wo_number)
        await asyncio.sleep(1)
        await page.keyboard.press('Enter')
        await asyncio.sleep(8)
        
        # Click on the work order in search results
        wo_link = await page.query_selector(f'text="{wo_number}"')
        if wo_link:
            await wo_link.click()
            await asyncio.sleep(5)
            log(f"✅ Opened work order {wo_number}")
        else:
            log(f"⚠️ Could not find work order {wo_number} in search results")
            return False
        
        # Now find and click the action button
        if action_type == 'accept':
            # Look for Accept button
            accept_btn = await page.query_selector('button:has-text("Accept"), a:has-text("Accept"), input[value="Accept"]')
            if accept_btn and 'cookie' not in (await accept_btn.get_attribute('class') or '').lower():
                await accept_btn.click()
                log(f"✅ Clicked Accept for {wo_number}")
                await asyncio.sleep(3)
                return True
            else:
                log(f"⚠️ No Accept button found for {wo_number}")
                return False
                
        elif action_type == 'decline':
            # Look for Decline/Reject button
            decline_btn = await page.query_selector('button:has-text("Decline"), button:has-text("Reject"), a:has-text("Decline"), a:has-text("Reject")')
            if decline_btn:
                await decline_btn.click()
                log(f"✅ Clicked Decline for {wo_number}")
                await asyncio.sleep(3)
                
                # Handle confirmation dialog if it appears
                confirm_btn = await page.query_selector('button:has-text("Confirm"), button:has-text("OK"), button:has-text("Yes")')
                if confirm_btn:
                    await confirm_btn.click()
                    await asyncio.sleep(2)
                
                return True
            else:
                log(f"⚠️ No Decline button found for {wo_number}")
                return False
                
        elif action_type == 'bid':
            # Look for Bid/Quote button
            bid_btn = await page.query_selector('button:has-text("Bid"), button:has-text("Quote"), a:has-text("Bid"), a:has-text("Submit Quote")')
            if bid_btn:
                await bid_btn.click()
                await asyncio.sleep(2)
                
                # Fill in bid amount if there's an input
                if bid_amount:
                    bid_input = await page.query_selector('input[type="number"], input[name*="bid" i], input[name*="amount" i], input[name*="quote" i]')
                    if bid_input:
                        await bid_input.fill(str(bid_amount))
                        await asyncio.sleep(1)
                
                # Submit
                submit_btn = await page.query_selector('button:has-text("Submit"), button:has-text("Send"), input[type="submit"]')
                if submit_btn:
                    await submit_btn.click()
                    log(f"✅ Submitted bid of ${bid_amount} for {wo_number}")
                    await asyncio.sleep(3)
                    return True
                else:
                    log(f"⚠️ Could not find submit button for bid")
                    return False
            else:
                log(f"⚠️ No Bid button found for {wo_number}")
                return False
        
        return False
        
    except Exception as e:
        log(f"❌ Error processing {wo_number}: {e}")
        return False

async def main_async():
    """Main execution."""
    log("=" * 50)
    log("Starting CorrigoPro automation cycle (Playwright)")
    log("=" * 50)

    # Load pending actions
    pending = load_pending_actions()

    if not pending:
        log("ℹ️ No pending actions found")
        return

    log(f"🚀 Processing {len(pending)} pending actions...")

    processed_ids = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Navigate to CorrigoPro
        await page.goto(CORRIGO_URL, timeout=60000)

        # Login if needed
        if 'login' in page.url.lower():
            if not await login_to_corrigo(page):
                log("❌ Login failed, aborting")
                await browser.close()
                return

        # Wait for dashboard
        await asyncio.sleep(5)

        # Process each action
        for action in pending:
            success = await process_action(page, action)
            if success:
                processed_ids.append(action['id'])
            await asyncio.sleep(2)

        await browser.close()

    # Mark processed actions
    if processed_ids:
        log(f"✅ Successfully processed {len(processed_ids)} actions")
        mark_actions_submitted(processed_ids)
    else:
        log("ℹ️ No actions were processed")

    log("=" * 50)
    log("CorrigoPro automation cycle complete")
    log("=" * 50)

if __name__ == '__main__':
    asyncio.run(main_async())