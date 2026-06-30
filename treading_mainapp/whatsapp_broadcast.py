import logging
import mimetypes
import os
from typing import Dict, List, Optional, Tuple

import requests
from django.conf import settings
from requests import Response
from requests.exceptions import RequestException, Timeout

logger = logging.getLogger(__name__)


class WhatsAppBroadcastError(Exception):
    pass


def normalize_indian_mobile(number: str) -> Optional[str]:
    if number is None:
        logger.warning("[WA] normalize_indian_mobile received None")
        return None

    raw = str(number).strip()
    digits = "".join(ch for ch in raw if ch.isdigit())

    logger.info("[WA] normalize_indian_mobile raw=%r digits=%r", raw, digits)

    if not digits:
        logger.warning("[WA] normalize_indian_mobile failed: empty digits")
        return None

    if digits.startswith("91") and len(digits) == 12:
        logger.info("[WA] normalize_indian_mobile matched 12-digit with country code result=%s", digits)
        return digits

    if len(digits) == 10:
        normalized = f"91{digits}"
        logger.info("[WA] normalize_indian_mobile matched 10-digit result=%s", normalized)
        return normalized

    if digits.startswith("0") and len(digits) == 11:
        trimmed = digits[1:]
        if len(trimmed) == 10:
            normalized = f"91{trimmed}"
            logger.info("[WA] normalize_indian_mobile matched leading-zero format result=%s", normalized)
            return normalized

    logger.warning("[WA] normalize_indian_mobile invalid raw=%r digits=%r", raw, digits)
    return None


def _clean_setting(name: str, default: str = "") -> str:
    value = getattr(settings, name, default)
    if value is None:
        return default
    return str(value).strip().strip('"').strip("'")


def _mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 8:
        return "****"
    return f"{token[:4]}...{token[-4:]}"


def get_whatsapp_config() -> Dict[str, str]:
    config = {
        "api_version": _clean_setting("WHATSAPP_API_VERSION", "v23.0"),
        "phone_number_id": _clean_setting("WHATSAPP_PHONE_NUMBER_ID"),
        "access_token": _clean_setting("WHATSAPP_ACCESS_TOKEN"),
        "business_account_id": _clean_setting("WHATSAPP_BUSINESS_ACCOUNT_ID"),
    }
    logger.info(
        "[WA] Config loaded api_version=%s phone_number_id=%s business_account_id=%s access_token=%s",
        config["api_version"],
        config["phone_number_id"],
        config["business_account_id"],
        _mask_token(config["access_token"]),
    )
    return config


def validate_whatsapp_config() -> Tuple[bool, List[str]]:
    config = get_whatsapp_config()
    missing = []

    if not config["phone_number_id"]:
        missing.append("WHATSAPP_PHONE_NUMBER_ID")
    if not config["access_token"]:
        missing.append("WHATSAPP_ACCESS_TOKEN")

    logger.info("[WA] Config validation result ok=%s missing=%s", len(missing) == 0, missing)
    return len(missing) == 0, missing


def get_api_base_url() -> str:
    config = get_whatsapp_config()
    base_url = f"https://graph.facebook.com/{config['api_version']}"
    logger.info("[WA] API base URL=%s", base_url)
    return base_url


def build_headers() -> Dict[str, str]:
    config = get_whatsapp_config()
    headers = {
        "Authorization": f"Bearer {config['access_token']}",
    }
    logger.info("[WA] Headers built authorization_token=%s", _mask_token(config["access_token"]))
    return headers


def detect_media_type(file_path: str) -> str:
    mime_type, _ = mimetypes.guess_type(file_path)
    mime_type = mime_type or ""

    logger.info("[WA] detect_media_type file_path=%r mime_type=%r", file_path, mime_type)

    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("video/"):
        return "video"
    return "document"


def _safe_json(response: Response) -> Dict:
    try:
        return response.json()
    except ValueError:
        logger.warning("[WA] Response is not valid JSON status=%s", response.status_code)
        return {}


def _response_text(response: Response) -> str:
    try:
        return response.text[:5000]
    except Exception:
        return "<unreadable response>"


def _raise_for_whatsapp_error(response: Response, action: str) -> None:
    if response.status_code in (200, 201):
        return

    payload = _safe_json(response)
    error = payload.get("error", {}) if isinstance(payload, dict) else {}

    message = error.get("message") or _response_text(response)
    code = error.get("code")
    error_type = error.get("type")
    error_subcode = error.get("error_subcode")
    fbtrace_id = error.get("fbtrace_id")

    detail_parts = [
        f"{action} failed",
        f"status={response.status_code}",
    ]
    if code is not None:
        detail_parts.append(f"code={code}")
    if error_subcode is not None:
        detail_parts.append(f"subcode={error_subcode}")
    if error_type:
        detail_parts.append(f"type={error_type}")
    if fbtrace_id:
        detail_parts.append(f"fbtrace_id={fbtrace_id}")
    if message:
        detail_parts.append(f"message={message}")

    error_text = " | ".join(detail_parts)
    logger.error("[WA] %s", error_text)
    raise WhatsAppBroadcastError(error_text)


def _post(url: str, *, headers: Dict[str, str], timeout: int = 60, **kwargs) -> Response:
    logger.info(
        "[WA] HTTP POST start url=%s timeout=%s has_json=%s has_data=%s has_files=%s",
        url,
        timeout,
        "json" in kwargs,
        "data" in kwargs,
        "files" in kwargs,
    )
    try:
        response = requests.post(url, headers=headers, timeout=timeout, **kwargs)
        logger.info(
            "[WA] HTTP POST end url=%s status=%s response=%r",
            url,
            response.status_code,
            _response_text(response)[:1000],
        )
        return response
    except Timeout as exc:
        logger.exception("[WA] HTTP POST timeout url=%s error=%s", url, exc)
        raise WhatsAppBroadcastError(f"WhatsApp API timeout error: {exc}") from exc
    except RequestException as exc:
        logger.exception("[WA] HTTP POST network error url=%s error=%s", url, exc)
        raise WhatsAppBroadcastError(f"WhatsApp API network error: {exc}") from exc


def upload_media_to_whatsapp(file_path: str) -> str:
    logger.info("[WA] upload_media_to_whatsapp started file_path=%r", file_path)

    config_ok, missing = validate_whatsapp_config()
    if not config_ok:
        raise WhatsAppBroadcastError(f"Missing WhatsApp config: {', '.join(missing)}")

    if not os.path.exists(file_path):
        logger.error("[WA] upload_media_to_whatsapp file not found path=%r", file_path)
        raise WhatsAppBroadcastError(f"Attachment file not found: {file_path}")

    file_size = os.path.getsize(file_path)
    logger.info("[WA] Media file exists path=%r size=%s", file_path, file_size)

    config = get_whatsapp_config()
    url = f"{get_api_base_url()}/{config['phone_number_id']}/media"

    mime_type, _ = mimetypes.guess_type(file_path)
    mime_type = mime_type or "application/octet-stream"

    logger.info("[WA] Uploading media file path=%r mime_type=%r url=%s", file_path, mime_type, url)

    with open(file_path, "rb") as file_obj:
        files = {
            "file": (os.path.basename(file_path), file_obj, mime_type),
        }
        data = {
            "messaging_product": "whatsapp",
        }
        response = _post(
            url,
            headers=build_headers(),
            files=files,
            data=data,
            timeout=120,
        )

    logger.info("[WA] Media upload response status=%s body=%r", response.status_code, _response_text(response))
    _raise_for_whatsapp_error(response, "Media upload")

    payload = _safe_json(response)
    media_id = payload.get("id")
    if not media_id:
        logger.error("[WA] Media upload succeeded but media id missing payload=%s", payload)
        raise WhatsAppBroadcastError("Media upload succeeded but media id not found.")

    logger.info("[WA] Media uploaded successfully media_id=%s", media_id)
    return str(media_id)


def send_text_message(to_number: str, message_text: str) -> Response:
    logger.info(
        "[WA] send_text_message started to=%s message_length=%s",
        to_number,
        len(message_text or ""),
    )

    config_ok, missing = validate_whatsapp_config()
    if not config_ok:
        raise WhatsAppBroadcastError(f"Missing WhatsApp config: {', '.join(missing)}")

    if not to_number:
        raise WhatsAppBroadcastError("Recipient phone number is missing.")

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
        "Accept": "application/json",
    }

    logger.info("[WA] Sending text message to=%s url=%s", to_number, url)
    response = _post(url, headers=headers, json=payload, timeout=60)
    logger.info("[WA] Text message response to=%s status=%s", to_number, response.status_code)
    return response


def send_media_message(
    to_number: str,
    media_id: str,
    media_type: str,
    caption: str = "",
) -> Response:
    logger.info(
        "[WA] send_media_message started to=%s media_id=%s media_type=%s caption_length=%s",
        to_number,
        media_id,
        media_type,
        len(caption or ""),
    )

    config_ok, missing = validate_whatsapp_config()
    if not config_ok:
        raise WhatsAppBroadcastError(f"Missing WhatsApp config: {', '.join(missing)}")

    if not to_number:
        raise WhatsAppBroadcastError("Recipient phone number is missing.")
    if not media_id:
        raise WhatsAppBroadcastError("media_id is required.")
    if media_type not in {"image", "video", "document"}:
        raise WhatsAppBroadcastError(f"Unsupported media type: {media_type}")

    config = get_whatsapp_config()
    url = f"{get_api_base_url()}/{config['phone_number_id']}/messages"

    media_payload = {"id": media_id}

    if caption:
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
        "Accept": "application/json",
    }

    logger.info("[WA] Sending media message to=%s url=%s media_type=%s", to_number, url, media_type)
    response = _post(url, headers=headers, json=payload, timeout=60)
    logger.info("[WA] Media message response to=%s status=%s", to_number, response.status_code)
    return response


def assert_success_response(response: Response, action: str = "Message send") -> Dict:
    logger.info("[WA] assert_success_response action=%s status=%s", action, response.status_code)
    _raise_for_whatsapp_error(response, action)
    payload = _safe_json(response)
    logger.info("[WA] assert_success_response payload=%s", payload)
    return payload