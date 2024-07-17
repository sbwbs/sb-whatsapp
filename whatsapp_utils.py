import logging
from fastapi import HTTPException
import json
import httpx
from typing import Dict, Any
from config import Config

logger = logging.getLogger(__name__)

async def send_whatsapp_message(to: str, text: str) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {Config.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(Config.WHATSAPP_API_URL, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            logger.info(f"WhatsApp API response: {response.status_code}, {response.text}")
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Error sending WhatsApp message: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to send WhatsApp message")

def is_valid_whatsapp_message(body: Dict[str, Any]) -> bool:
    return (
        body.get("object") == "whatsapp_business_account"
        and body.get("entry")
        and isinstance(body["entry"], list)
        and len(body["entry"]) > 0
        and body["entry"][0].get("changes")
        and isinstance(body["entry"][0]["changes"], list)
        and len(body["entry"][0]["changes"]) > 0
        and body["entry"][0]["changes"][0].get("value")
        and body["entry"][0]["changes"][0].get("field") == "messages"
    )

def extract_whatsapp_message(body: Dict[str, Any]) -> Dict[str, Any]:
    value = body["entry"][0]["changes"][0]["value"]
    metadata = value.get("metadata", {})
    messages = value.get("messages", [])
    
    if not messages:
        raise ValueError("No messages found in the webhook payload")
    
    message = messages[0]
    return {
        "from_number": message.get("from"),
        "text": message.get("text", {}).get("body", ""),
        "phone_number_id": metadata.get("phone_number_id"),
        "display_phone_number": metadata.get("display_phone_number")
    }