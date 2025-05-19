from datetime import datetime, timedelta
from jose import jwt, JWTError
import os

from ..config import settings

# Ideally, load these from your config/env!
SECRET_KEY = settings.jwt.secret_key
ALGORITHM = settings.jwt.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.jwt.access_token_expire_minutes


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
