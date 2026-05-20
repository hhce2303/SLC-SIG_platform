
from MySQLdb import connect
from dotenv import dotenv_values

_env = dotenv_values(".env")


def test_sigtools_db_connection():
    connection = None
    try:
        connection = connect(
            host=_env.get("SIGTOOLS_DB_HOST", "72.167.56.142"),
            port=int(_env.get("SIGTOOLS_DB_PORT", 3306)),
            user=_env["SIGTOOLS_DB_USER"],
            password=_env["SIGTOOLS_DB_PASSWORD"],
            database=_env.get("SIGTOOLS_DB_NAME", "sigtools_beta"),
        )
        cursor = connection.cursor()
        cursor.execute("SELECT 1")  # Simple query to test connectivity
        result = cursor.fetchone()
        assert result == (1,), "Unexpected query result, DB connection may be faulty."
        print("Successfully connected to sigtools_beta and executed test query.")

    except Exception as exc:
        raise AssertionError(f"Failed to connect to sigtools_beta: {exc}")

    finally:
        if connection:
            connection.close()


            