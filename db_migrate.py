import sqlite3
import os
from app import init_db, get_db


def upgrade_db_add_availability():
    """Add availability columns to the employees table."""
    db = get_db()
    # Check if columns already exist
    cols = db.execute("PRAGMA table_info(employees)").fetchall()
    col_names = [c["name"] for c in cols]

    if "availability" not in col_names:
        db.execute("ALTER TABLE employees ADD COLUMN availability TEXT DEFAULT ''")
    if "unavailable_days" not in col_names:
        db.execute("ALTER TABLE employees ADD COLUMN unavailable_days TEXT DEFAULT ''")
    db.commit()
    db.close()


if __name__ == "__main__":
    init_db()
    upgrade_db_add_availability()
    print("DB upgraded with availability columns")
