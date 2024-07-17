import hashlib
import hmac
from fastapi import HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import Config

def validate_signature(payload: bytes, signature: str) -> bool:
    expected_signature = hmac.new(
        bytes(Config.APP_SECRET, "latin-1"),
        msg=payload,
        digestmod=hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)

class SignatureBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super(SignatureBearer, self).__init__(auto_error=auto_error)

    async def __call__(self, request):
        credentials: HTTPAuthorizationCredentials = await super(SignatureBearer, self).__call__(request)
        if credentials:
            if not credentials.scheme == "sha256":
                raise HTTPException(status_code=403, detail="Invalid authentication scheme.")
            if not validate_signature(await request.body(), credentials.credentials):
                raise HTTPException(status_code=403, detail="Invalid signature.")
            return credentials.credentials
        else:
            raise HTTPException(status_code=403, detail="Invalid authorization code.")

signature_auth = SignatureBearer()

def verify_webhook(mode: str, token: str, challenge: str) -> str:
    if mode and token:
        if mode == "subscribe" and token == Config.VERIFY_TOKEN:
            return challenge
        else:
            raise HTTPException(status_code=403, detail="Verification failed.")
    else:
        raise HTTPException(status_code=403, detail="Invalid verification parameters.")