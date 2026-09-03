from datetime import datetime, timedelta, timezone
import secrets, jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from .config import get_settings
_password_hasher = PasswordHasher()
ALGORITHM = "HS256"

def hash_password(password): return _password_hasher.hash(password)
def verify_password(password, hashed):
    try: return _password_hasher.verify(hashed, password)
    except (VerifyMismatchError, VerificationError): return False

def create_access_token(user_id, session_id=None):
    now=datetime.now(timezone.utc); s=get_settings()
    return jwt.encode({"sub":str(user_id),"type":"access","iat":now,"exp":now+timedelta(minutes=s.access_token_minutes),"jti":secrets.token_urlsafe(16),"session_id":session_id},s.jwt_secret,algorithm=ALGORITHM)

def create_refresh_token(user_id):
    now=datetime.now(timezone.utc); s=get_settings(); jti=secrets.token_urlsafe(24)
    return jwt.encode({"sub":str(user_id),"type":"refresh","iat":now,"exp":now+timedelta(days=s.refresh_token_days),"jti":jti},s.jwt_secret,algorithm=ALGORITHM),jti

def decode_token(token): return jwt.decode(token,get_settings().jwt_secret,algorithms=[ALGORITHM])
