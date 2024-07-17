from fastapi import FastAPI, Request, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
import httpx
import logging
from security import signature_auth, verify_webhook

app = FastAPI()

# Load environment variables
# load_dotenv()

WHATSAPP_ACCESS_TOKEN = "EAA3p7berstcBO6TRmIvbLscX4kDPKyh3mDlqxwOIKLjPpYCqtJ7QCC6DPKtoUUWbGWLZB9yhUigGDdOLKWlz7uuHjfnNdbqqaMF5fmBlouv780cz2o2uYZBZCAz3t65r0hz6ObXcCnK6uBjmjyD3aKL61SSVueVTbKcM56rOemEDpmBVRA1rsXKj2QWZAtkbpuGeT0zD9Ju9HbZBoVZC4ZD"
WHATSAPP_PHONE_NUMBER_ID = "239939252545624"
WHATSAPP_VERSION = "v20.0"
WHATSAPP_ID = "3916381895242455"

# Sendbird API configuration
SENDBIRD_API_URL = "https://api-5237C2C5-10EC-4503-8252-5660D788B433.sendbird.com/v3"
SENDBIRD_API_TOKEN = "fa184516a0c6f9ef9b85a7a8f28b93f6f24b7cdf"
BOT_USER_ID = "XM3bHWtOOFKkE7DklvZql"

# WhatsApp API configuration
WHATSAPP_API_URL = f"https://graph.facebook.com/{WHATSAPP_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"

# In-memory cache to track messages
whatsapp_messages = {}

class WhatsAppMessage(BaseModel):
    object: str
    entry: list

@app.get("/webhook")
async def verify_webhook_subscription(
    mode: str = Query(..., alias="hub.mode"),
    token: str = Query(..., alias="hub.verify_token"),
    challenge: str = Query(..., alias="hub.challenge")
):
    logging.info(f"Received webhook verification request: mode={mode}, token={token}, challenge={challenge}")
    result = verify_webhook(mode, token, challenge)
    logging.info(f"Webhook verified successfully. Returning challenge: {challenge}")
    return PlainTextResponse(content=result)


@app.post("/webhook")
async def handle_whatsapp_webhook(message: WhatsAppMessage, signature: str = Depends(signature_auth)):
    logging.info(f"Received webhook payload: {message}")
    
    if message.object == "whatsapp_business_account":
        for entry in message.entry:
            for change in entry.get("changes", []):
                if change.get("field") == "messages":
                    for msg in change.get("value", {}).get("messages", []):
                        if msg.get("type") == "text":
                            await process_incoming_message(msg)
                elif change.get("field") == "message_status_updates":
                    logging.info("Received a WhatsApp status update.")
    else:
        raise HTTPException(status_code=404, detail="Not a WhatsApp API event")
    
    return {"status": "ok"}

async def process_incoming_message(msg):
    from_number = msg["from"]
    message_body = msg["text"]["body"]
    
    print(f"[DEBUG] Received message from {from_number}: {message_body}")
    
    # Ensure the user exists in Sendbird
    user = await create_sendbird_user(from_number)
    if not user:
        print(f"[ERROR] Failed to create or retrieve user {from_number} in Sendbird")
        return

    # Send message to Sendbird
    channel_url = await send_distinct_message(from_number, BOT_USER_ID, message_body)
    
    if channel_url:
        whatsapp_messages[from_number] = {'message': message_body, 'channel_url': channel_url}
        print(f"[DEBUG] Message sent to Sendbird: channel_url={channel_url}")
    else:
        print(f"[ERROR] Failed to send message to Sendbird for user {from_number}")

@app.post("/sbwebhook")
async def handle_sendbird_webhook(request: Request):
    payload = await request.json()
    print(f"[DEBUG] Received Sendbird webhook payload: {payload}")
    
    if payload.get('category') == 'group_channel:message_send':
        channel_url = payload['channel']['channel_url']
        sender_id = payload['sender']['user_id']
        message = payload['payload']['message']
        print(f"[DEBUG] Received message from Sendbird: channel_url={channel_url}, sender_id={sender_id}, message='{message}'")
        
        # Only send the message to WhatsApp if it's from the bot
        if sender_id == BOT_USER_ID:
            for user_id, data in whatsapp_messages.items():
                if data['channel_url'] == channel_url:
                    print(f"[DEBUG] Sending bot response to WhatsApp: user_id={user_id}, message='{message}'")
                    await send_whatsapp_message(user_id, message)
                    break
    
    return {"status": "ok"}

async def create_sendbird_user(user_id: str):
    async with httpx.AsyncClient() as client:
        create_user_url = f"{SENDBIRD_API_URL}/users"
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Api-Token": SENDBIRD_API_TOKEN
        }
        payload = {
            "user_id": user_id,
            "nickname": user_id,
            "profile_url": "",
            "issue_access_token": True
        }
        create_response = await client.post(create_user_url, headers=headers, json=payload)
        if create_response.status_code == 200:
            print(f"User {user_id} created successfully.")
            return create_response.json()
        elif create_response.status_code == 400 and create_response.json().get("code") == 400202:
            print(f"User {user_id} already exists.")
            return {"user_id": user_id}
        else:
            print(f"Failed to create user {user_id}: {create_response.json()}")
            return None

async def send_distinct_message(sender_id: str, receiver_id: str, message: str):
    async with httpx.AsyncClient() as client:
        send_message_url = f"{SENDBIRD_API_URL}/group_channels/distinct_message"
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Api-Token": SENDBIRD_API_TOKEN
        }
        payload = {
            "sender_id": sender_id,
            "receiver_ids": [receiver_id],
            "message_payload": {
                "message_type": "MESG",
                "message": message,
                "user_id": sender_id
            },
            "create_channel": True
        }
        response = await client.post(send_message_url, headers=headers, json=payload)
        if response.status_code == 200:
            response_data = response.json()
            print(f"Message sent successfully: {response_data}")
            return response_data['channel_url']
        else:
            print(f"Failed to send message: {response.json()}")
            return None

async def send_whatsapp_message(to, text):
    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }
        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        response = await client.post(WHATSAPP_API_URL, headers=headers, json=data)
        print(f"[DEBUG] WhatsApp API response: {response.status_code}, {response.text}")
        return response

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
