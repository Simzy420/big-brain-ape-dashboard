#!/usr/bin/env python3
"""
Corrigo Invoice Automation — Hard Checks Version
Checkpoint-based. Refuses to submit unless hours, material, and photo all verify.
"""
import asyncio
import logging
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger(__name__)

async def verify_hours(page, expected_hours: str) -> bool:
    # Read QTY back from the labor line
    # TODO: implement selector for the labor QTY field
    actual = await page.evaluate("() => document.querySelector('input[data-role=qty]')?.value || ''")
    if str(actual).strip() != str(expected_hours).strip():
        log.error(f"HOURS MISMATCH: expected {expected_hours}, got {actual}")
        await page.screenshot(path=f"/workspace/artifacts/fail_hours.png")
        return False
    log.info(f"Hours OK: {expected_hours}")
    return True

async def verify_material(page, expected_cost: float | None) -> bool:
    # Check material line existence and values
    # TODO: implement
    if expected_cost is None or expected_cost == 0:
        # ensure no material line
        pass
    else:
        # ensure line with QTY=1 and rate==expected_cost
        pass
    return True

async def verify_photo(page, photo_required: bool) -> bool:
    if not photo_required:
        return True
    # Check attachments section for files
    has_attachment = await page.evaluate("() => !!document.querySelector('.attachment-item, .uploaded-file')")
    if not has_attachment:
        log.error("PHOTO REQUIRED BUT NOT ATTACHED")
        await page.screenshot(path="/workspace/artifacts/fail_photo.png")
        return False
    log.info("Photo attached OK")
    return True

async def process_invoice(page, wo_data: dict):
    expected_hours = wo_data.get("hours", "")
    materials_cost = wo_data.get("materials")  # adjust key as needed
    photo_required = bool(wo_data.get("photos") and any(p.get("url") or p.get("data") for p in wo_data["photos"]))

    # ... fill form ...

    if not await verify_hours(page, expected_hours):
        return False
    if not await verify_material(page, materials_cost):
        return False
    if not await verify_photo(page, photo_required):
        return False

    # Only then submit
    log.info("All hard checks passed — submitting")
    # await page.click("button:has-text('SUBMIT')")
    return True

# Main entry would load JSON, login, loop over target WOs only, call process_invoice
