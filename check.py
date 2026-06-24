"""
Single-cycle check of the cadastre application status page.

Run periodically (by GitHub Actions cron). Loads docs/status.json to see
what we last knew, checks the live page via a stealth-Playwright browser
(the site blocks plain HTTP requests as bot traffic), and if the number of
"ready to collect" documents has newly become non-zero, sends an SMS.
"""
import asyncio
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from config import HEADLESS, KAIS_URL, NOTIFY_MESSAGE, NOTIFY_PHONE, REG_NUMBER
from notify import send_sms

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

STATUS_FILE = Path("docs/status.json")
DEBUG_DIR = Path("debug")
MAX_RETRIES = 3
LOCAL_TZ = ZoneInfo("Europe/Sofia")


def _read_status() -> dict:
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _write_status(fields: dict, ready_count: int | None, last_notified_count, error: str | None) -> None:
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(LOCAL_TZ)
    data = {
        "timestamp": now_local.strftime("%Y-%m-%d %H:%M"),
        "timestamp_utc": now_utc.isoformat(),
        "reg_number": REG_NUMBER,
        "ready_documents": ready_count,
        "status": fields.get("Статус"),
        "registered_on": fields.get("Регистриран на"),
        "payment_status": fields.get("Статус на плащане"),
        "office": fields.get("Служба по изп."),
        "stage": fields.get("Текущо изпълняван етап"),
        "last_notified_count": last_notified_count,
        "error": error,
    }
    STATUS_FILE.parent.mkdir(exist_ok=True)
    STATUS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Status written: ready_documents=%s error=%s", ready_count, error)


def _parse_result(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    doc_row = soup.select_one(".doc-row")
    if doc_row is None:
        return {}
    fields = {}
    for div in doc_row.select(".doc-text > div"):
        strong = div.find("strong")
        if not strong:
            continue
        value = strong.get_text(strip=True)
        label = div.get_text(strip=True)
        label = label[: label.rfind(value)].strip().rstrip(":").strip()
        fields[label] = value
    return fields


async def _fetch_result_html() -> str:
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        try:
            page = await browser.new_page()
            await page.goto(KAIS_URL, wait_until="networkidle")
            target_id = await page.get_attribute("form.checkform", "data-ajax-update")
            target_selector = f'[id="{target_id.lstrip("#")}"]'
            await page.fill('input[name="RegNumber"]', REG_NUMBER)
            await page.click('form.checkform button[type="submit"]')
            await page.wait_for_timeout(5000)
            return await page.inner_html(target_selector)
        except Exception:
            DEBUG_DIR.mkdir(exist_ok=True)
            await page.screenshot(path=str(DEBUG_DIR / "error.png"), full_page=True)
            raise
        finally:
            await browser.close()


async def run() -> None:
    previous = _read_status()
    last_notified_count = previous.get("last_notified_count")

    html = None
    error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            html = await _fetch_result_html()
            break
        except Exception as exc:
            logger.warning("Attempt %d/%d failed: %s", attempt, MAX_RETRIES, exc)
            error = str(exc)
            await asyncio.sleep(5)

    if html is None:
        logger.error("All attempts failed — keeping previous status")
        _write_status(previous, previous.get("ready_documents"), last_notified_count, error)
        sys.exit(1)

    fields = _parse_result(html)
    if not fields:
        logger.warning("Could not find a result row for %s — site may be down or number invalid", REG_NUMBER)
        _write_status(previous, previous.get("ready_documents"), last_notified_count, "No result row found")
        return

    raw_count = fields.get("Готови документи за получаване", "0")
    match = re.search(r"\d+", raw_count)
    ready_count = int(match.group()) if match else 0

    logger.info("Ready documents: %d  (status: %s)", ready_count, fields.get("Статус"))

    if ready_count > 0 and ready_count != last_notified_count:
        logger.info("New ready documents detected — sending SMS to %s", NOTIFY_PHONE)
        if send_sms(NOTIFY_PHONE, NOTIFY_MESSAGE):
            last_notified_count = ready_count
        else:
            logger.error("SMS send failed — will retry next run")
    elif ready_count == 0:
        last_notified_count = None

    _write_status(fields, ready_count, last_notified_count, None)


if __name__ == "__main__":
    asyncio.run(run())
