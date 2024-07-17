import logging
import httpx
from fastapi import HTTPException
from config import Config

logger = logging.getLogger(__name__)

async def create_sendbird_user(user_id: str):
    async with httpx.AsyncClient() as client:
        create_user_url = f"{Config.SENDBIRD_API_URL}/users"
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Api-Token": Config.SENDBIRD_API_TOKEN
        }
        payload = {
            "user_id": user_id,
            "nickname": user_id,
            "profile_url": "",
            "issue_access_token": True
        }
        try:
            response = await client.post(create_user_url, headers=headers, json=payload)
            response.raise_for_status()
            logger.info(f"User {user_id} created or already exists in Sendbird.")
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400 and e.response.json().get("code") == 400202:
                logger.info(f"User {user_id} already exists in Sendbird.")
                return {"user_id": user_id}
            else:
                logger.error(f"Failed to create user {user_id} in Sendbird: {str(e)}")
                raise HTTPException(status_code=500, detail="Failed to create Sendbird user")

async def send_sendbird_message(sender_id: str, receiver_id: str, message: str):
    async with httpx.AsyncClient() as client:
        send_message_url = f"{Config.SENDBIRD_API_URL}/group_channels"
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Api-Token": Config.SENDBIRD_API_TOKEN
        }
        payload = {
            "user_ids": [sender_id, receiver_id],
            "is_distinct": True,
            "message": message
        }
        try:
            response = await client.post(f"{send_message_url}/create", headers=headers, json=payload)
            response.raise_for_status()
            channel_url = response.json()["channel_url"]
            
            message_payload = {
                "message_type": "MESG",
                "user_id": sender_id,
                "message": message
            }
            message_response = await client.post(f"{send_message_url}/{channel_url}/messages", headers=headers, json=message_payload)
            message_response.raise_for_status()
            
            logger.info(f"Message sent successfully to Sendbird channel: {channel_url}")
            return channel_url
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to send message to Sendbird: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to send Sendbird message")