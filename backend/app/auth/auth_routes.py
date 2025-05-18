from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from backend.app.db.users import get_user_by_email, create_user
from backend.app.auth.utils import hash_password, verify_password
from backend.app.auth.jwt import create_access_token

auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    org_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@auth_router.post("/signup")
def signup(data: SignupRequest):
    if get_user_by_email(data.email):
        raise HTTPException(status_code=400, detail="Email already registered.")
    password_hash = hash_password(data.password)
    user = create_user(data.email, password_hash, data.org_name)
    access_token = create_access_token({"user_id": user["id"], "email": data.email})
    return {"access_token": access_token, "token_type": "bearer"}


@auth_router.post("/login")
def login(data: LoginRequest):
    user = get_user_by_email(data.email)
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Invalid credentials.")
    access_token = create_access_token({"user_id": user["id"], "email": data.email})
    return {"access_token": access_token, "token_type": "bearer"}
