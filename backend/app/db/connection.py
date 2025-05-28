# backend/app/db/connection.py
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from loguru import logger

from backend.app.config import settings

_connection_pool = None


def initialize_connection_pool():
    global _connection_pool
    if _connection_pool is None:
        try:
            logger.info("Initializing PostgreSQL connection pool...")

            min_conn = getattr(settings.database, "min_connections", 1)
            max_conn = getattr(settings.database, "max_connections", 10)

            _connection_pool = pool.SimpleConnectionPool(
                minconn=min_conn,
                maxconn=max_conn,
                user=settings.database.user,
                password=settings.database.password,
                host=settings.database.host,
                port=settings.database.port,
                dbname=settings.database.dbname,
            )
            if _connection_pool:
                logger.success(
                    f"PostgreSQL connection pool initialized (min: {min_conn}, max: {max_conn})."
                )
            else:
                logger.error(
                    "Failed to initialize PostgreSQL connection pool: Pool object is None after creation attempt."
                )

                raise ConnectionError("Failed to initialize DB pool: Pool is None.")
        except (Exception, psycopg2.DatabaseError) as error:
            logger.critical(
                f"Error while initializing PostgreSQL connection pool: {error}",
                exc_info=True,
            )
            _connection_pool = None

            raise ConnectionError(f"Failed to initialize DB pool: {error}") from error
    else:
        logger.debug("PostgreSQL connection pool already initialized.")


def close_connection_pool():
    global _connection_pool

    if _connection_pool:
        logger.info("Closing PostgreSQL connection pool...")
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("PostgreSQL connection pool closed.")


@contextmanager
def get_db_connection():
    if _connection_pool is None:
        logger.error(
            "Connection pool is not initialized. Attempting to initialize now."
        )
        initialize_connection_pool()

        if _connection_pool is None:
            raise ConnectionError(
                "Database connection pool is not available and could not be initialized."
            )

    conn = None
    try:
        conn = _connection_pool.getconn()
        logger.trace("Connection acquired from pool.")

        yield conn
    except Exception as e:
        logger.error(
            f"Error acquiring or using connection from pool: {e}", exc_info=True
        )
        raise
    finally:
        if conn:
            _connection_pool.putconn(conn)
            logger.trace("Connection returned to pool.")


def fetch_one(query, params=None):
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                return cursor.fetchone()
    except (Exception, psycopg2.Error) as error:
        logger.error(
            f"DB Error in fetch_one for query '{query[:100]}...': {error}",
            exc_info=True,
        )
        raise


def fetch_all(query, params=None):
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()
    except (Exception, psycopg2.Error) as error:
        logger.error(
            f"DB Error in fetch_all for query '{query[:100]}...': {error}",
            exc_info=True,
        )
        raise
    return []


def execute_query(query, params=None):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
            conn.commit()

            return True
    except (Exception, psycopg2.Error) as error:
        logger.error(
            f"DB Error in execute_query for query '{query[:100]}...': {error}",
            exc_info=True,
        )

        raise
    return False


def execute_and_fetch_one(query, params=None):
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                row = cursor.fetchone()
            conn.commit()
            return row
    except (Exception, psycopg2.Error) as error:
        logger.error(
            f"DB Error in execute_and_fetch_one for query '{query[:100]}...': {error}",
            exc_info=True,
        )
        raise
    return None
