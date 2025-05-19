import uuid
from typing import Optional

from .connection import fetch_one, execute_query
from .schemas import UserInDB


def get_user_by_email(email: str) -> Optional[UserInDB]:
    query = "SELECT * FROM users WHERE email = %s"
    user_data = fetch_one(query, (email,))

    return UserInDB.model_validate(user_data) if user_data else None


def get_user_by_id(user_id: uuid.UUID) -> Optional[UserInDB]:
    query = "SELECT * FROM users WHERE id = %s"
    user_data = fetch_one(query, (str(user_id),))

    return UserInDB.model_validate(user_data) if user_data else None


def create_user(email: str, password_hash: str, org_name: str) -> UserInDB:
    query = """
    INSERT INTO users (email, password_hash, org_name)
    VALUES (%s, %s, %s)
    RETURNING id, email, password_hash, org_name, created_at
    """
    user_data = fetch_one(query, (email, password_hash, org_name))

    return UserInDB.model_validate(user_data)
