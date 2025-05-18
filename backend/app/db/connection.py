import psycopg2
from psycopg2.extras import RealDictCursor
from backend.app.config import settings


def get_connection():
    conn = psycopg2.connect(
        user=settings.database.user,
        password=settings.database.password,
        host=settings.database.host,
        port=settings.database.port,
        dbname=settings.database.dbname,
    )

    return conn


def fetch_one(query, params=None):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)

            return cursor.fetchone()


def fetch_all(query, params=None):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)

            return cursor.fetchall()


def execute_query(query, params=None):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            conn.commit()
