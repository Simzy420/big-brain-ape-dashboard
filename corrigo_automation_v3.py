#!/usr/bin/env python3
"""
CorrigoPro Automation - Playwright-based
1. Read Gary's accept/decline/bid/update actions from GitHub (corrigo-actions.json)
2. Log into CorrigoPro
3. Filter to "Waiting for Acceptance" work orders
4. For accept/decline/bid: Find work order and click the button Gary chose
5. For update: Find work order, open completion details, paste work description
6. Leave immediately - do nothing else
"""
import asyncio
import json
import os
import base64
from datetime import datetime
from playwright.async_api import async_playwright
import requests

# Configuration
CORRIGO_USERNAME = os.environ.get("CORRIGO_USERNAME", "")
CORRIGO_PASSWORD = os.environ.get("CORRIGO_PASSWORD", "")
CORRIGO_URL = "https://am-desktop.corrigopro.com/"
ACTIONS_FILE = "corrigo-actions.json"
GITHUB_REPO = "Simzy420/big-brain-ape-dashboard"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", os.environ.get("GITHUB_TOKEN_SIMZY", ""))
LOG_FILE = "/workspace/corrigo_automation.log"

def log(message):
    timestamp = datetime.now().isoformat()
    entry = f"[{timestamp}] {message}"
    with open(LOG_FILE, 'a') as f:
        f.write(entry + "\n")
    print(entry)

def load_pending_actions():
    """Load pending actions from GitHub."""
    try:
        url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{ACTIONS_FILE}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            actions = data.get('pendingActions', [])
            log(f"Loaded {len(actions)} pending actions")
            return actions
        else:
            log(f"No actions file (HTTP {response.status_code})")
            return []
    except Exception as e:
        log(f"Error loading actions: {e}")
        return []

def mark_actions_submitted(processed_ids):
    """Clear processed actions from corrigo-actions.json on GitHub."""
    if not processed_ids:
        return
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{ACTIONS_FILE}"
        headers = {'Authorization': f'token {GITHUB_TOKEN}', 'Content-Type': 'application/json'}

        # Get current file SHA
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            log(f"Could not get file SHA: {resp.status_code}")
            return
        sha = resp.json().get('sha')

        # Load current actions
        current = requests.get(
            f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{ACTIONS_FILE}",
            timeout=10
        ).json()

        remaining = [a for a in current.get('pendingActions', []) if a['id'] not in processed_ids]

        export_data = {
            'pendingActions': remaining,
            'exportedAt': datetime.now().isoformat(),
            'count': len(remaining)
        }

        data = {
            'message': f'Processed {len(processed_ids)} actions on CorrigoPro',
            'content': base64.b64encode(json.dumps(export_data, indent=2).encode()).decode(),
        }
        if sha:
            data['sha'] = sha

        resp = requests.put(url, headers=headers, json=data, timeout=10)
        if resp.status_code in [200, 201]:
            log(f"Cleared {len(processed_ids)} processed actions")
        else:
            log(f"Failed to update: {resp.status_code}")
    except Exception as e:
        log(f"Error marking actions: {e}")

async def login_to_corrigo(page):
    """Login to CorrigoPro."""
    try:
        log("Logging into CorrigoPro...")
        await page.wait_for_selector('input[name="UserName"]', timeout=15000)
        await page.fill('input[name="UserName"]', CORRIGO_USERNAME)
        await page.fill('input[name="Password"]', CORRIGO_PASSWORD)
        await page.click('input[type="submit"]')
        await page.wait_for_load_state('domcontentloaded', timeout=30000)
        await asyncio.sleep(5)
        if 'login' not in page.url.lower():
            log("Logged in successfully")
            return True
        else:
            log("Login failed - still on login page")
            return False
    except Exception as e:
        log(f"Login error: {e}")
        return False

async def filter_waiting_for_acceptance(page):
    """
    Filter work orders to show only "Waiting for Acceptance".
    Steps (from Casey's screenshots):
    1. Open the WO STATE dropdown
    2. Click "Waiting for Acceptance" to check it
    3. Uncheck "Completed" if it's checked
    4. Make sure ONLY "Waiting for Acceptance" is checked
    """
    try:
        log("Filtering to Waiting for Acceptance...")

        # Find the WO STATE dropdown - it's a bootstrap-select
        # Look for the dropdown toggle that contains "WO STATE"
        wo_state_dropdown = await page.query_selector('.filter-container .bootstrap-select .dropdown-toggle')
        if wo_state_dropdown:
            await wo_state_dropdown.click()
            await asyncio.sleep(1)
        else:
            # Try alternative selectors
            dropdowns = await page.query_selector_all('.dropdown-toggle')
            for d in dropdowns:
                text = await d.inner_text()
                if 'WO STATE' in text or 'Waiting' in text or 'Open' in text:
                    await d.click()
                    await asyncio.sleep(1)
                    break

        # Now find and click "Waiting for Acceptance" option
        # Options are <a> tags inside the dropdown
        wait_accept_option = await page.query_selector('a:has-text("Waiting for Acceptance")')
        if wait_accept_option:
            await wait_accept_option.click()
            await asyncio.sleep(1)
            log("Clicked 'Waiting for Acceptance'")

        # Uncheck "Completed" if it has a checkmark
        completed_option = await page.query_selector('a:has-text("Completed")')
        if completed_option:
            # Check if it's selected (has 'selected' class or similar)
            parent = await completed_option.evaluate('el => el.parentElement')
            parent_class = await completed_option.evaluate('el => el.parentElement.className')
            if 'selected' in parent_class:
                await completed_option.click()
                await asyncio.sleep(1)
                log("Unchecked 'Completed'")

        # Close dropdown by clicking elsewhere
        await page.keyboard.press('Escape')
        await asyncio.sleep(2)

        log("Filter applied: Waiting for Acceptance only")
        return True

    except Exception as e:
        log(f"Filter error: {e}")
        return False

async def process_action(page, action):
    """
    Process a single action:
    1. Search for the work order by number
    2. Click on it to open details
    3. Find and click Accept/Decline/Bid button
    4. Confirm if needed
    5. Leave
    """
    wo_number = action['number']
    action_type = action['action'].lower()
    bid_amount = action.get('bidAmount')

    log(f"Processing {wo_number} - Action: {action_type}")

    try:
        # Navigate back to main dashboard before each search
        await page.goto(CORRIGO_URL, timeout=60000)
        await asyncio.sleep(3)
        
        # Search for the work order - try multiple search methods
        search_box = await page.wait_for_selector('#header-search', timeout=10000)
        await search_box.fill('')
        await search_box.fill(wo_number)
        await asyncio.sleep(1)
        await page.keyboard.press('Enter')
        await asyncio.sleep(8)

        # Click on the work order in search results
        wo_link = await page.query_selector(f'text="{wo_number}"')
        if not wo_link:
            # Try partial match - sometimes CorrigoPro formats numbers differently
            # e.g. the dash might be different or there's a prefix
            partial = wo_number.split('-')[0]
            wo_link = await page.query_selector(f'text="{partial}"')
        
        if wo_link:
            await wo_link.click()
            await asyncio.sleep(5)
            log(f"Opened work order {wo_number}")
        else:
            log(f"Could not find work order {wo_number} in search results")
            return False

        # Now find and click the action button
        # Based on screenshots, buttons appear when work order is in "Waiting for Acceptance" state

        if action_type == 'accept':
            # Look for Accept button (not the cookie policy one)
            buttons = await page.query_selector_all('button, a, input[type="submit"], input[type="button"]')
            for btn in buttons:
                text = await btn.inner_text()
                if text and 'accept' in text.strip().lower():
                    btn_class = await btn.get_attribute('class') or ''
                    btn_id = await btn.get_attribute('id') or ''
                    # Skip cookie policy button
                    if 'cookie' in btn_class or 'policy' in btn_id:
                        continue
                    await btn.click()
                    log(f"Clicked Accept for {wo_number}")
                    await asyncio.sleep(3)

                    # Handle confirmation dialog if it appears
                    confirm = await page.query_selector('button:has-text("Confirm"), button:has-text("OK"), button:has-text("Yes"), button:has-text("Accept")')
                    if confirm:
                        confirm_class = await confirm.get_attribute('class') or ''
                        confirm_id = await confirm.get_attribute('id') or ''
                        if 'cookie' not in confirm_class and 'policy' not in confirm_id:
                            await confirm.click()
                            await asyncio.sleep(2)
                    return True
            log(f"No Accept button found for {wo_number}")
            return False

        # After accept/decline, if there's a work description, add it to completion details
        if action_type in ['accept', 'update'] and action.get('workDescription'):
            work_description = action['workDescription']
            log(f"Adding work description to {wo_number}")

            # Look for "Specify completion details" button - scroll to find it
            specify_btn = await page.query_selector('a:has-text("Specify completion details"), button:has-text("Specify completion details"), a:has-text("completion"), button:has-text("completion")')
            
            if not specify_btn:
                # Button might be below the fold - scroll down to find it
                for scroll_attempt in range(5):
                    await page.evaluate(f'window.scrollBy(0, 500)')
                    await asyncio.sleep(1)
                    specify_btn = await page.query_selector('a:has-text("Specify completion details"), button:has-text("Specify completion details"), a:has-text("completion"), button:has-text("completion")')
                    if specify_btn:
                        break
                
                # Also try scrolling within any scrollable containers
                if not specify_btn:
                    await page.evaluate('document.querySelectorAll(".tab-content, .panel-body, .card-body, [style*=\"overflow\"]").forEach(el => el.scrollTop = el.scrollHeight)')
                    await asyncio.sleep(2)
                    specify_btn = await page.query_selector('a:has-text("Specify completion details"), button:has-text("Specify completion details"), a:has-text("completion"), button:has-text("completion")')
            
            if specify_btn:
                # Scroll the button into view before clicking
                await specify_btn.scroll_into_view_if_needed()
                await asyncio.sleep(1)
                await specify_btn.click()
                await asyncio.sleep(5)
                log("Opened completion details page")

                # Find the WORK DONE DESCRIPTION textarea
                desc_field = None
                textareas = await page.query_selector_all('textarea')
                for ta in textareas:
                    ta_id = await ta.get_attribute('id') or ''
                    ta_name = await ta.get_attribute('name') or ''
                    ta_ph = await ta.get_attribute('placeholder') or ''
                    if any(k in (ta_id + ta_name + ta_ph).lower() for k in ['desc', 'work', 'done', 'completion']):
                        desc_field = ta
                        break
                if not desc_field and textareas:
                    desc_field = textareas[-1]

                if desc_field:
                    await desc_field.fill('')
                    await desc_field.fill(work_description)
                    log(f"Entered work description for {wo_number}")

                    save_btn = await page.query_selector('button:has-text("Save"), button:has-text("Submit"), input[type="submit"], button:has-text("Update")')
                    if save_btn:
                        await save_btn.click()
                        await asyncio.sleep(3)
                        log(f"Saved work description for {wo_number}")
                    else:
                        log(f"Could not find save button")
                else:
                    log(f"Could not find description field")
            else:
                log(f"No completion details button found for {wo_number}")

        elif action_type == 'decline':
            # Look for Decline/Reject button
            buttons = await page.query_selector_all('button, a, input[type="submit"], input[type="button"]')
            for btn in buttons:
                text = await btn.inner_text()
                if text and ('decline' in text.strip().lower() or 'reject' in text.strip().lower()):
                    await btn.click()
                    log(f"Clicked Decline for {wo_number}")
                    await asyncio.sleep(3)

                    # Handle confirmation dialog
                    confirm = await page.query_selector('button:has-text("Confirm"), button:has-text("OK"), button:has-text("Yes")')
                    if confirm:
                        await confirm.click()
                        await asyncio.sleep(2)
                    return True
            log(f"No Decline button found for {wo_number}")
            return False

        elif action_type == 'bid':
            # Look for Bid/Quote button
            buttons = await page.query_selector_all('button, a, input[type="submit"], input[type="button"]')
            for btn in buttons:
                text = await btn.inner_text()
                if text and ('bid' in text.strip().lower() or 'quote' in text.strip().lower()):
                    await btn.click()
                    await asyncio.sleep(2)

                    # Fill in bid amount if there's an input
                    if bid_amount:
                        bid_input = await page.query_selector('input[type="number"], input[name*="bid" i], input[name*="amount" i], input[name*="quote" i]')
                        if bid_input:
                            await bid_input.fill(str(bid_amount))
                            await asyncio.sleep(1)

                    # Submit
                    submit = await page.query_selector('button:has-text("Submit"), button:has-text("Send"), input[type="submit"]')
                    if submit:
                        await submit.click()
                        log(f"Submitted bid of ${bid_amount} for {wo_number}")
                        await asyncio.sleep(3)
                        return True
                    else:
                        log(f"Could not find submit button for bid")
                        return False
            log(f"No Bid button found for {wo_number}")
            return False


        elif action_type == 'update':
            # Work order completion - fill in all completion details and submit
            work_description = action.get('workDescription', '')
            hours = action.get('hours', '')
            rate = action.get('rate', '')
            date_started = action.get('dateStarted', '')
            date_completed = action.get('dateCompleted', '')
            invoice_number = action.get('invoiceNumber', '')
            
            if not work_description and not hours:
                log(f"No work data for {wo_number}")
                return False

            log(f"Adding completion details to {wo_number}: desc={work_description[:40]}... hours={hours} rate={rate}")

            # Search for the work order
            search_box = await page.wait_for_selector('#header-search', timeout=10000)
            await search_box.fill('')
            await search_box.fill(wo_number)
            await asyncio.sleep(1)
            await page.keyboard.press('Enter')
            await asyncio.sleep(8)

            # Click on the work order
            wo_link = await page.query_selector(f'text="{wo_number}"')
            if wo_link:
                await wo_link.click()
                await asyncio.sleep(5)
                log(f"Opened work order {wo_number}")
            else:
                log(f"Could not find work order {wo_number}")
                return False

            # Look for "Specify completion details" button or link - scroll to find it
            specify_btn = await page.query_selector('a:has-text("Specify completion details"), button:has-text("Specify completion details"), a:has-text("completion"), button:has-text("completion")')
            
            if not specify_btn:
                # Button might be below the fold - scroll down to find it
                for scroll_attempt in range(5):
                    await page.evaluate(f'window.scrollBy(0, 500)')
                    await asyncio.sleep(1)
                    specify_btn = await page.query_selector('a:has-text("Specify completion details"), button:has-text("Specify completion details"), a:has-text("completion"), button:has-text("completion")')
                    if specify_btn:
                        break
                
                # Also try scrolling within scrollable containers
                if not specify_btn:
                    await page.evaluate('document.querySelectorAll(".tab-content, .panel-body, .card-body, [style*=\"overflow\"]").forEach(el => el.scrollTop = el.scrollHeight)')
                    await asyncio.sleep(2)
                    specify_btn = await page.query_selector('a:has-text("Specify completion details"), button:has-text("Specify completion details"), a:has-text("completion"), button:has-text("completion")')
            
            if specify_btn:
                await specify_btn.scroll_into_view_if_needed()
                await asyncio.sleep(1)
                await specify_btn.click()
                await asyncio.sleep(5)
                log("Opened completion details page")
            else:
                # Try clicking any link that contains "completion"
                links = await page.query_selector_all('a, button')
                for link in links:
                    text = await link.inner_text()
                    if text and 'completion' in text.strip().lower():
                        await link.click()
                        await asyncio.sleep(5)
                        log(f"Clicked completion link: {text}")
                        break

            # Fill in WORK DONE DESCRIPTION textarea
            desc_field = await page.query_selector('textarea[name*="description" i], textarea[name*="work" i], textarea[placeholder*="description" i], textarea[placeholder*="work" i]')
            if not desc_field:
                desc_field = await page.query_selector('#workDoneDescription, textarea[id*="description" i], textarea[id*="work" i]')
            if not desc_field:
                textareas = await page.query_selector_all('textarea')
                for ta in textareas:
                    ta_id = await ta.get_attribute('id') or ''
                    ta_name = await ta.get_attribute('name') or ''
                    ta_ph = await ta.get_attribute('placeholder') or ''
                    if 'desc' in ta_id.lower() or 'desc' in ta_name.lower() or 'desc' in ta_ph.lower() or 'work' in ta_id.lower() or 'work' in ta_name.lower():
                        desc_field = ta
                        break
                if not desc_field and len(textareas) > 0:
                    desc_field = textareas[-1]

            if desc_field and work_description:
                await desc_field.fill('')
                await desc_field.fill(work_description)
                log(f"Entered work description for {wo_number}")
            else:
                log(f"Could not find WORK DONE DESCRIPTION field for {wo_number}")

            # Fill in HOURS field
            if hours:
                hours_field = await page.query_selector('input[name*="hour" i], input[id*="hour" i], input[name*="time" i], input[placeholder*="hour" i]')
                if not hours_field:
                    # Try number inputs
                    number_inputs = await page.query_selector_all('input[type="number"], input[type="text"]')
                    for ni in number_inputs:
                        ni_name = await ni.get_attribute('name') or ''
                        ni_id = await ni.get_attribute('id') or ''
                        ni_ph = await ni.get_attribute('placeholder') or ''
                        ni_label = ni_name + ni_id + ni_ph
                        if any(k in ni_label.lower() for k in ['hour', 'time', 'labor', 'duration']):
                            hours_field = ni
                            break
                if hours_field:
                    await hours_field.fill('')
                    await hours_field.fill(str(hours))
                    log(f"Entered hours: {hours}")
                else:
                    log(f"Could not find hours field")

            # Fill in RATE field
            if rate:
                rate_field = await page.query_selector('input[name*="rate" i], input[id*="rate" i], input[name*="cost" i], input[placeholder*="rate" i]')
                if not rate_field:
                    number_inputs = await page.query_selector_all('input[type="number"], input[type="text"]')
                    for ni in number_inputs:
                        ni_name = await ni.get_attribute('name') or ''
                        ni_id = await ni.get_attribute('id') or ''
                        ni_ph = await ni.get_attribute('placeholder') or ''
                        ni_label = ni_name + ni_id + ni_ph
                        if any(k in ni_label.lower() for k in ['rate', 'cost', 'price']):
                            rate_field = ni
                            break
                if rate_field:
                    await rate_field.fill('')
                    await rate_field.fill(str(rate))
                    log(f"Entered rate: {rate}")
                else:
                    log(f"Could not find rate field")

            # Fill in DATE STARTED field
            if date_started:
                date_start_field = await page.query_selector('input[name*="start" i], input[id*="start" i], input[type="date"]:nth-of-type(1), input[placeholder*="start" i]')
                if not date_start_field:
                    date_inputs = await page.query_selector_all('input[type="date"], input[placeholder*="date" i], input[name*="date" i]')
                    if len(date_inputs) >= 1:
                        date_start_field = date_inputs[0]
                if date_start_field:
                    await date_start_field.fill('')
                    await date_start_field.fill(date_started)
                    log(f"Entered date started: {date_started}")

            # Fill in DATE COMPLETED field
            if date_completed:
                date_comp_field = await page.query_selector('input[name*="complete" i], input[id*="complete" i], input[name*="end" i], input[placeholder*="complete" i]')
                if not date_comp_field:
                    date_inputs = await page.query_selector_all('input[type="date"], input[placeholder*="date" i], input[name*="date" i]')
                    if len(date_inputs) >= 2:
                        date_comp_field = date_inputs[1]
                    elif len(date_inputs) == 1:
                        date_comp_field = date_inputs[0]
                if date_comp_field:
                    await date_comp_field.fill('')
                    await date_comp_field.fill(date_completed)
                    log(f"Entered date completed: {date_completed}")

            # Fill in INVOICE NUMBER field
            if invoice_number:
                invoice_field = await page.query_selector('input[name*="invoice" i], input[id*="invoice" i], input[placeholder*="invoice" i]')
                if not invoice_field:
                    text_inputs = await page.query_selector_all('input[type="text"]')
                    for ti in text_inputs:
                        ti_name = await ti.get_attribute('name') or ''
                        ti_id = await ti.get_attribute('id') or ''
                        if 'invoice' in ti_name.lower() or 'invoice' in ti_id.lower():
                            invoice_field = ti
                            break
                if invoice_field:
                    await invoice_field.fill('')
                    await invoice_field.fill(invoice_number)
                    log(f"Entered invoice number: {invoice_number}")

            # Look for Save/Submit button
            save_btn = await page.query_selector('button:has-text("Save"), button:has-text("Submit"), input[type="submit"], button:has-text("Update"), button:has-text("Complete")')
            if save_btn:
                await save_btn.click()
                await asyncio.sleep(3)
                log(f"Saved completion details for {wo_number}")
                
                # Look for a final Submit/Confirm button if one appears
                final_submit = await page.query_selector('button:has-text("Submit"), button:has-text("Confirm"), button:has-text("OK"), button:has-text("Yes")')
                if final_submit:
                    final_class = await final_submit.get_attribute('class') or ''
                    if 'cookie' not in final_class:
                        await final_submit.click()
                        await asyncio.sleep(3)
                        log(f"Final submission confirmed for {wo_number}")
                
                return True
            else:
                log(f"Could not find save button for {wo_number}")
                return False

        return False

    except Exception as e:
        log(f"Error processing {wo_number}: {e}")
        return False

async def main_async():
    """Main execution."""
    log("=" * 50)
    log("Starting CorrigoPro automation cycle")
    log("=" * 50)

    # Check credentials
    if not CORRIGO_USERNAME or not CORRIGO_PASSWORD:
        log("ERROR: Missing CorrigoPro credentials")
        return
    if not GITHUB_TOKEN:
        log("ERROR: Missing GitHub token")
        return

    # Load pending actions
    pending = load_pending_actions()
    if not pending:
        log("No pending actions found")
        return

    log(f"Processing {len(pending)} pending actions...")

    processed_ids = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Navigate to CorrigoPro
        await page.goto(CORRIGO_URL, timeout=60000)

        # Login if needed
        if 'login' in page.url.lower():
            if not await login_to_corrigo(page):
                log("Login failed, aborting")
                await browser.close()
                return

        # Wait for dashboard
        await asyncio.sleep(5)

        # Only filter to Waiting for Acceptance if all actions are accept/decline/bid
        action_types = [a.get('action', '').lower() for a in pending]
        needs_acceptance_filter = all(t in ['accept', 'decline', 'bid'] for t in action_types)
        
        if needs_acceptance_filter:
            await filter_waiting_for_acceptance(page)
        else:
            # For update/dispute/resolve actions, work orders are already accepted
            # Need to clear any default filters so search can find them
            log("Skipping Waiting for Acceptance filter (update/dispute actions)")
            # Try to clear filters - look for a "Clear" or "Reset" button
            try:
                clear_btn = await page.query_selector('button:has-text("Clear"), button:has-text("Reset"), a:has-text("Clear"), a:has-text("Reset")')
                if clear_btn:
                    await clear_btn.click()
                    await asyncio.sleep(2)
                    log("Cleared filters")
            except:
                pass

        # Process each action
        for action in pending:
            success = await process_action(page, action)
            if success:
                processed_ids.append(action['id'])
            await asyncio.sleep(2)

        await browser.close()

    # Mark processed actions
    if processed_ids:
        log(f"Successfully processed {len(processed_ids)} actions")
        mark_actions_submitted(processed_ids)
    else:
        log("No actions were processed")

    log("=" * 50)
    log("Automation cycle complete")
    log("=" * 50)

if __name__ == '__main__':
    asyncio.run(main_async())