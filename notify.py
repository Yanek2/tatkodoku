"""Sends an SMS via the Twilio REST API using plain HTTP (no SDK needed)."""
import logging
import os

import requests

logger = logging.getLogger(__name__)

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "")


def send_sms(to_number: str, body: str) -> bool:
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER):
        logger.error("Twilio credentials not set (TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN/TWILIO_FROM_NUMBER)")
        return False

    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    try:
        resp = requests.post(
            url,
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            data={"From": TWILIO_FROM_NUMBER, "To": to_number, "Body": body},
            timeout=20,
        )
    except requests.RequestException as exc:
        logger.error("SMS request failed: %s", exc)
        return False

    if resp.status_code >= 300:
        logger.error("Twilio error %s: %s", resp.status_code, resp.text)
        return False

    logger.info("SMS sent to %s", to_number)
    return True
