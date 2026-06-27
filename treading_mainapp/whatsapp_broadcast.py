import logging
import mimetypes
import os
from typing import Dict, List, Tuple

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class WhatsAppBroadcastError(Exception):
    pass


def normalize_indian_mobile(number: str):
    digits = "".join(ch for ch in str(number) if ch.isdigit())

    if not digits:
        return None

    if digits.startswith("91") and len(digits) == 12:
        return digits

    if len(digits) == 10:
        return f"91{digits}"

    if digits.startswith("0") and len(digits) == 11:
        trimmed = digits[1:]
        if len(trimmed) == 10:
            return f"91{trimmed}"

    return None


def get_whatsapp_config() -> Dict[str, str]:
    return {
        "api_version": getattr(settings, "WHATSAPP_API_VERSION", "v23.0"),
        "phone_number_id": getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", ""),
        "access_token": getattr(settings, "WHATSAPP_ACCESS_TOKEN", ""),
        "business_account_id": getattr(settings, "WHATSAPP_BUSINESS_ACCOUNT_ID", ""),
    }


def validate_whatsapp_config() -> Tuple[bool, List[str]]:
    config = get_whatsapp_config()
    missing = []

    if not config["phone_number_id"]:
        missing.append("WHATSAPP_PHONE_NUMBER_ID")
    if not config["access_token"]:
        missing.append("WHATSAPP_ACCESS_TOKEN")

    return len(missing) == 0, missing


def get_api_base_url() -> str:
    config = get_whatsapp_config()
    return f"https://graph.facebook.com/{config['api_version']}"


def build_headers() -> Dict[str, str]:
    config = get_whatsapp_config()
    return {
        "Authorization": f"Bearer {config['access_token']}",
    }


def detect_media_type(file_path: str) -> str:
    mime_type, _ = mimetypes.guess_type(file_path)
    mime_type = mime_type or ""

    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("video/"):
        return "video"
    return "document"


def upload_media_to_whatsapp(file_path: str) -> str:
    config = get_whatsapp_config()
    url = f"{get_api_base_url()}/{config['phone_number_id']}/media"

    mime_type, _ = mimetypes.guess_type(file_path)
    mime_type = mime_type or "application/octet-stream"

    logger.info("Uploading media file: %s", file_path)

    with open(file_path, "rb") as file_obj:
        files = {
            "file": (os.path.basename(file_path), file_obj, mime_type),
        }
        data = {
            "messaging_product": "whatsapp",
        }
        response = requests.post(
            url,
            headers=build_headers(),
            files=files,
            data=data,
            timeout=60,
        )

    logger.info("Media upload response: %s %s", response.status_code, response.text)

    if response.status_code not in (200, 201):
        raise WhatsAppBroadcastError(
            f"Media upload failed ({response.status_code}): {response.text}"
        )

    payload = response.json()
    media_id = payload.get("id")
    if not media_id:
        raise WhatsAppBroadcastError("Media upload succeeded but media id not found.")

    return media_id


def send_text_message(to_number: str, message_text: str) -> requests.Response:
    config = get_whatsapp_config()
    url = f"{get_api_base_url()}/{config['phone_number_id']}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": message_text,
        },
    }

    headers = {
        **build_headers(),
        "Content-Type": "application/json",
    }

    logger.info("Sending text message to %s", to_number)
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    logger.info("Text message response: %s %s", response.status_code, response.text)
    return response


def send_media_message(to_number: str, media_id: str, media_type: str, caption: str = "") -> requests.Response:
    config = get_whatsapp_config()
    url = f"{get_api_base_url()}/{config['phone_number_id']}/messages"

    media_payload = {"id": media_id}

    if media_type in ["image", "video", "document"] and caption:
        media_payload["caption"] = caption

    if media_type == "document":
        media_payload["filename"] = "broadcast-file"

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": media_type,
        media_type: media_payload,
    }

    headers = {
        **build_headers(),
        "Content-Type": "application/json",
    }

    logger.info("Sending media message to %s", to_number)
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    logger.info("Media message response: %s %s", response.status_code, response.text)
    return response