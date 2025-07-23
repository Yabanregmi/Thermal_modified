import sqlite3

def try_db_connect(db_path):
    try:
        conn = sqlite3.connect(db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS temperatures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wert REAL,
                zeit TEXT,
                checksum TEXT
            );
        ''')
        return conn
    except Exception as e:
        print(f"[DB] Fehler bei Verbindung/Aufbau: {e}")
        return None

def write_batch(conn, db_values, max_rows):
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM temperatures")
        row_count = cur.fetchone()[0]
        if row_count + len(db_values) > max_rows:
            delete_count = (row_count + len(db_values)) - max_rows
            conn.execute(
                f"DELETE FROM temperatures WHERE id IN (SELECT id FROM temperatures ORDER BY id ASC LIMIT {delete_count})"
            )
            conn.commit()
        conn.executemany(
            "INSERT INTO temperatures (wert, zeit, checksum) VALUES (?, ?, ?)",
            db_values
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"[DB] Fehler beim Schreiben: {e}")
        return False
