import sqlite3

db = "diecast_store.db"
connection = sqlite3.connect(db)
cursor = connection.cursor()

try:
    print("Database integrity:")
    print(cursor.execute("PRAGMA integrity_check").fetchall())

    print("\nTables found:")
    print(cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall())

except sqlite3.DatabaseError as error:
    print("Database error:", error)

finally:
    connection.close()