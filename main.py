from fastapi import FastAPI, Request, Depends, HTTPException, Query, Body
from fastapi.responses import JSONResponse, PlainTextResponse
import logging
import json
from security import signature_auth, verify_webhook
from whatsapp_utils import is_valid_whatsapp_message, extract_whatsapp_message, send_whatsapp_message
from sendbird_utils import create_sendbird_user, send_sendbird_message
from config import Config
from pydantic import BaseModel, Field
from typing import List, Optional

class WhatsAppMessage(BaseModel):
    from_: str = Field(..., alias="from")
    id: str
    timestamp: str
    text: Optional[dict] = None
    type: str

class WhatsAppValue(BaseModel):
    messaging_product: str
    metadata: dict
    contacts: Optional[List[dict]] = None
    messages: Optional[List[WhatsAppMessage]] = None

class WhatsAppChange(BaseModel):
    value: WhatsAppValue
    field: str

class WhatsAppEntry(BaseModel):
    id: str
    changes: List[WhatsAppChange]

class WhatsAppWebhook(BaseModel):
    object: str
    entry: List[WhatsAppEntry]

app = FastAPI()
# Logging
# Setup logging
Config.setup_logging()
logger = logging.getLogger(__name__)

# In-memory cache to track messages
whatsapp_messages = {}

@app.get("/webhook")
async def verify_webhook_subscription(
    mode: str = Query(..., alias="hub.mode"),
    token: str = Query(..., alias="hub.verify_token"),
    challenge: str = Query(..., alias="hub.challenge")
):
    logger.info(f"Received webhook verification request: mode={mode}, token={token}, challenge={challenge}")
    result = verify_webhook(mode, token, challenge)
    logger.info(f"Webhook verified successfully. Returning challenge: {challenge}")
    return PlainTextResponse(content=result)

@app.post("/webhook")
# async def handle_whatsapp_webhook(request: Request, signature: str = Depends(signature_auth)):
#     try:
#         raw_body = await request.body()
#         print(f"Raw webhook payload: {raw_body.decode()}")
#         logger.info(f"Raw webhook payload: {raw_body}")

#         # body = await request.json()
#          # Parse the JSON body
#         body = json.loads(raw_body)
#         logger.info(f"Parsed webhook payload: {body}")

#         if is_valid_whatsapp_message(body):
#             try:
#                 wa_message = extract_whatsapp_message(body)
#                 print(f"Extracted WhatsApp message: {wa_message}")
#                 sendbird_user = await create_sendbird_user(wa_message["from_number"])
#                 channel_url = await send_sendbird_message(sendbird_user["user_id"], Config.BOT_USER_ID, wa_message["text"])
#                 whatsapp_messages[wa_message["from_number"]] = channel_url
#                 return JSONResponse(content={"status": "ok"})
#             except ValueError as ve:
#                 print(f"Invalid message format: {str(ve)}")
#                 return JSONResponse(content={"status": "ok"})  # Acknowledge receipt even if we can't process it
#         else:
#             print("Received a non-message WhatsApp update.")
#             return JSONResponse(content={"status": "ok"})  # Acknowledge receipt of other types of updates
#     except json.JSONDecodeError:
#         print("Failed to decode JSON")
#         raise HTTPException(status_code=400, detail="Invalid JSON provided")
#     except Exception as e:
#         print(f"Error processing webhook: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
async def handle_whatsapp_webhook(
    webhook: WhatsAppWebhook = Body(...),
    signature: str = Depends(signature_auth)
):
    try:
        logger.info(f"Received webhook payload: {webhook}")

        for entry in webhook.entry:
            for change in entry.changes:
                if change.field == "messages":
                    for message in change.value.messages or []:
                        if message.type == "text":
                            wa_message = {
                                "from_number": message.from_,
                                "text": message.text.get("body", "") if message.text else ""
                            }
                            print(f"Extracted WhatsApp message: {wa_message}")
                            sendbird_user = await create_sendbird_user(wa_message["from_number"])
                            channel_url = await send_sendbird_message(sendbird_user["user_id"], Config.BOT_USER_ID, wa_message["text"])
                            whatsapp_messages[wa_message["from_number"]] = channel_url

        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/sbwebhook")
async def handle_sendbird_webhook(request: Request):
    payload = await request.json()
    logger.info(f"Received Sendbird webhook payload: {payload}")
    
    if payload.get('category') == 'group_channel:message_send':
        channel_url = payload['channel']['channel_url']
        sender_id = payload['sender']['user_id']
        message = payload['payload']['message']
        logger.info(f"Received message from Sendbird: channel_url={channel_url}, sender_id={sender_id}, message='{message}'")
        
        if sender_id == Config.BOT_USER_ID:
            for user_id, stored_channel_url in whatsapp_messages.items():
                if stored_channel_url == channel_url:
                    logger.info(f"Sending bot response to WhatsApp: user_id={user_id}, message='{message}'")
                    await send_whatsapp_message(user_id, message)
                    break
    
    return JSONResponse(content={"status": "ok"})

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    logger.error(f"HTTP error occurred: {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)