from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr

from ..db.users import get_user_by_email, create_user
from ..db.schemas import UserCreateInput

from .utils import hash_password, verify_password
from .jwt import create_access_token

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@auth_router.post("/signup")
def signup(data: UserCreateInput):
    if get_user_by_email(data.email):
        raise HTTPException(status_code=400, detail="Email already registered.")
    password_hash = hash_password(data.password)
    user_db_data = create_user(data.email, password_hash, data.org_name)
    access_token = create_access_token(
        {
            "user_id": str(user_db_data.id),
            "email": data.email,
            "org_name": user_db_data.org_name,
        }
    )
    return {"access_token": access_token, "token_type": "bearer"}


@auth_router.post("/login")
def login(data: LoginRequest):
    user_db_data = get_user_by_email(data.email)
    if not user_db_data or not verify_password(
        data.password, user_db_data.password_hash
    ):
        raise HTTPException(status_code=400, detail="Invalid credentials.")
    access_token = create_access_token(
        {
            "user_id": str(user_db_data.id),
            "email": user_db_data.email,
            "org_name": user_db_data.org_name,
        }
    )
    return {"access_token": access_token, "token_type": "bearer"}
