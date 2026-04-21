"""
Quick migration to add skill domain and file fields
"""
import sqlite3

DB_PATH = "smartlink.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Add domain column
    try:
        cursor.execute("ALTER TABLE skills ADD COLUMN domain VARCHAR(50) DEFAULT 'resource'")
        print("Added domain column")
    except sqlite3.OperationalError as e:
        print(f"domain: {e}")
    
    # Add other columns
    columns = [
        ("visibility", "VARCHAR(20) DEFAULT 'public'"),
        ("author", "VARCHAR(255)"),
        ("maintainer", "VARCHAR(255)"),
        ("license", "VARCHAR(100)"),
        ("tags", "JSON DEFAULT '[]'"),
        ("icon", "VARCHAR(255)"),
        ("risk_level", "VARCHAR(20) DEFAULT 'low'"),
        ("requires_approval", "BOOLEAN DEFAULT 0"),
        ("input_schema", "JSON DEFAULT '{}'"),
        ("output_schema", "JSON DEFAULT '{}'"),
        ("stats", "JSON DEFAULT '{}'"),
        ("current_version", "VARCHAR(32) DEFAULT '1.0.0'"),
        ("files", "VARCHAR(255)"),  # placeholder
        ("versions", "VARCHAR(255)"),  # placeholder
    ]
    
    for col_name, col_type in columns:
        try:
            cursor.execute(f"ALTER TABLE skills ADD COLUMN {col_name} {col_type}")
            print(f"Added {col_name} column")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e):
                print(f"{col_name}: {e}")
    
    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()