from backend.app.db.connection import fetch_one, fetch_all, execute_query


def get_user_by_email(email):
    query = "SELECT * FROM users WHERE email = %s"
    return fetch_one(query, (email,))


def create_user(email, password_hash, org_name):
    query = """
        INSERT INTO users (email, password_hash, org_name)
        VALUES (%s, %s, %s)
        RETURNING id, email, org_name
    """
    return fetch_one(query, (email, password_hash, org_name))
