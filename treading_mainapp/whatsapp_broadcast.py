import json
import logging
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class BroadcastRecipient:
    username: str
    mobile: str
    email: str = ""


@dataclass
class BroadcastResult:
    mobile: str
    username: str
    success: bool
    status_code: int
    response_text: str


class WhatsAppBroadcastError(Exception):
    pass


def normalize_indian_mobile(number: str) -> Optional[str]:
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


def load_recipients_from_json(json_path: str) -> List[BroadcastRecipient]:
    path = Path(json_path)
    if not path.exists():
        raise WhatsAppBroadcastError(f"JSON file not found: {json_path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise WhatsAppBroadcastError("JSON file must contain a list of users.")

    recipients = []
    seen = set()

    for item in data:
        if not isinstance(item, dict):
            continue

        raw_mobile = item.get("mobile", "")
        normalized = normalize_indian_mobile(raw_mobile)
        if not normalized:
            continue

        if normalized in seen:
            continue

        seen.add(normalized)
        recipients.append(
            BroadcastRecipient(
                username=item.get("username", "Unknown"),
                mobile=normalized,
                email=item.get("email", "")
            )
        )

    return recipients


def get_whatsapp_config() -> Dict[str, str]:
    return {
        "api_version": getattr(settings, "WHATSAPP_API_VERSION", "v20.0"),
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


def upload_media_to_whatsapp(file_path: str) -> str:
    config = get_whatsapp_config()
    url = f"{get_api_base_url()}/{config['phone_number_id']}/media"

    mime_type, _ = mimetypes.guess_type(file_path)
    mime_type = mime_type or "application/octet-stream"

    with open(file_path, "rb") as file_obj:
        files = {
            "file": (os.path.basename(file_path), file_obj, mime_type),
        }
        data = {
            "messaging_product": "whatsapp",
        }
        response = requests.post(url, headers=build_headers(), files=files, data=data, timeout=60)

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

    return requests.post(url, headers=headers, json=payload, timeout=60)


def send_media_message(to_number: str, media_id: str, media_type: str, caption: str = "") -> requests.Response:
    config = get_whatsapp_config()
    url = f"{get_api_base_url()}/{config['phone_number_id']}/messages"

    media_payload = {
        "id": media_id,
    }

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

    return requests.post(url, headers=headers, json=payload, timeout=60)


def detect_media_type(file_path: str) -> str:
    mime_type, _ = mimetypes.guess_type(file_path)
    mime_type = mime_type or ""

    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("video/"):
        return "video"
    return "document"


def broadcast_whatsapp_message(message_text: str, uploaded_file_path: Optional[str] = None) -> Dict:
    json_path = getattr(settings, "WHATSAPP_CONTACTS_JSON", "")
    if not json_path:
        raise WhatsAppBroadcastError("WHATSAPP_CONTACTS_JSON is not configured.")

    is_valid, missing = validate_whatsapp_config()
    if not is_valid:
        raise WhatsAppBroadcastError(
            f"Missing WhatsApp config: {', '.join(missing)}"
        )

    recipients = load_recipients_from_json(json_path)
    if not recipients:
        raise WhatsAppBroadcastError("No valid recipients found in JSON file.")

    results: List[BroadcastResult] = []

    media_id = None
    media_type = None

    if uploaded_file_path:
        media_type = detect_media_type(uploaded_file_path)
        media_id = upload_media_to_whatsapp(uploaded_file_path)

    for recipient in recipients:
        try:
            if media_id and media_type:
                response = send_media_message(
                    to_number=recipient.mobile,
                    media_id=media_id,
                    media_type=media_type,
                    caption=message_text or ""
                )
            else:
                response = send_text_message(
                    to_number=recipient.mobile,
                    message_text=message_text
                )

            success = response.status_code in (200, 201)
            results.append(
                BroadcastResult(
                    mobile=recipient.mobile,
                    username=recipient.username,
                    success=success,
                    status_code=response.status_code,
                    response_text=response.text,
                )
            )
        except Exception as exc:
            logger.exception("Broadcast failed for %s", recipient.mobile)
            results.append(
                BroadcastResult(
                    mobile=recipient.mobile,
                    username=recipient.username,
                    success=False,
                    status_code=500,
                    response_text=str(exc),
                )
            )

    success_count = sum(1 for item in results if item.success)
    failed_count = len(results) - success_count

    return {
        "total": len(results),
        "success_count": success_count,
        "failed_count": failed_count,
        "results": results,
    }