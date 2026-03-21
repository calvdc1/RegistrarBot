import os
import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime


def resolve_db_file():
    """Choose a database path, preferring persistent storage when available."""
    configured_path = os.getenv("DB_FILE")
    if configured_path:
        return configured_path

    configured_dir = os.getenv("DB_DIR")
    if configured_dir:
        return str(Path(configured_dir) / "attendance.db")

    candidate_dirs = []
    persistent_dir = Path("/data")
    if persistent_dir.exists() and persistent_dir.is_dir():
        candidate_dirs.append(persistent_dir)

    candidate_dirs.append(Path("data"))

    for directory in candidate_dirs:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            return str(directory / "attendance.db")
        except OSError:
            continue

    return "attendance.db"


DB_FILE = resolve_db_file()
SNAPSHOT_FILE = os.getenv("DB_SNAPSHOT_FILE", str(Path(DB_FILE).with_name("attendance_snapshot.json")))
logger = logging.getLogger(__name__)


def write_snapshot():
    """Writes a JSON backup snapshot beside the SQLite database."""
    try:
        snapshot_path = Path(SNAPSHOT_FILE)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        payload = export_all_data()
        snapshot_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8"
        )
    except Exception as e:
        logger.warning("Failed to write snapshot %s: %s", SNAPSHOT_FILE, e)


def export_all_data():
    """Exports the database contents as plain JSON-serializable structures."""
    conn = get_connection()
    c = conn.cursor()

    tables = {}
    for table_name in ("guild_configs", "attendance_records", "attendance_stats", "custom_commands"):
        c.execute(f"SELECT * FROM {table_name}")
        tables[table_name] = [dict(row) for row in c.fetchall()]

    conn.close()
    return {
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "db_file": DB_FILE,
        "tables": tables
    }


def is_database_empty(conn):
    """Returns True when all persisted tables are empty."""
    c = conn.cursor()
    for table_name in ("guild_configs", "attendance_records", "attendance_stats", "custom_commands"):
        c.execute(f"SELECT COUNT(*) AS count FROM {table_name}")
        row = c.fetchone()
        if row and row["count"]:
            return False
    return True


def restore_snapshot_if_needed(conn):
    """Restores the JSON snapshot into a new empty database."""
    snapshot_path = Path(SNAPSHOT_FILE)
    if not snapshot_path.exists() or not is_database_empty(conn):
        return

    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        tables = payload.get("tables", {})
        c = conn.cursor()

        c.executemany(
            '''INSERT INTO guild_configs (
                   guild_id, attendance_role_id, absent_role_id, excused_role_id,
                   welcome_channel_id, report_channel_id, last_report_message_id,
                   last_report_channel_id, attendance_mode, attendance_expiry_hours,
                   window_start_time, window_end_time, last_processed_date,
                   last_opened_date, allow_self_marking, require_admin_excuse,
                   auto_nick_on_join, enforce_suffix, remove_suffix_on_role_loss,
                   suffix_format, present_channel_id
               ) VALUES (
                   :guild_id, :attendance_role_id, :absent_role_id, :excused_role_id,
                   :welcome_channel_id, :report_channel_id, :last_report_message_id,
                   :last_report_channel_id, :attendance_mode, :attendance_expiry_hours,
                   :window_start_time, :window_end_time, :last_processed_date,
                   :last_opened_date, :allow_self_marking, :require_admin_excuse,
                   :auto_nick_on_join, :enforce_suffix, :remove_suffix_on_role_loss,
                   :suffix_format, :present_channel_id
               )''',
            tables.get("guild_configs", [])
        )
        c.executemany(
            '''INSERT INTO attendance_records (
                   id, guild_id, user_id, status, timestamp, channel_id, reason
               ) VALUES (
                   :id, :guild_id, :user_id, :status, :timestamp, :channel_id, :reason
               )''',
            tables.get("attendance_records", [])
        )
        c.executemany(
            '''INSERT INTO attendance_stats (
                   guild_id, user_id, present_count, absent_count, excused_count
               ) VALUES (
                   :guild_id, :user_id, :present_count, :absent_count, :excused_count
               )''',
            tables.get("attendance_stats", [])
        )
        c.executemany(
            '''INSERT INTO custom_commands (
                   guild_id, command_name, response_text
               ) VALUES (
                   :guild_id, :command_name, :response_text
               )''',
            tables.get("custom_commands", [])
        )

        conn.commit()
        logger.info("Restored database contents from snapshot %s", snapshot_path)
    except Exception as e:
        conn.rollback()
        logger.warning("Failed to restore snapshot %s: %s", snapshot_path, e)

def get_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database tables."""
    conn = get_connection()
    c = conn.cursor()
    
    # Guild Configuration Table
    c.execute('''CREATE TABLE IF NOT EXISTS guild_configs (
        guild_id INTEGER PRIMARY KEY,
        attendance_role_id INTEGER,
        absent_role_id INTEGER,
        excused_role_id INTEGER,
        welcome_channel_id INTEGER,
        report_channel_id INTEGER,
        last_report_message_id INTEGER,
        last_report_channel_id INTEGER,
        attendance_mode TEXT DEFAULT 'duration',
        attendance_expiry_hours INTEGER DEFAULT 12,
        window_start_time TEXT DEFAULT '08:00',
        window_end_time TEXT DEFAULT '17:00',
        last_processed_date TEXT,
        last_opened_date TEXT,
        allow_self_marking BOOLEAN DEFAULT 1,
        require_admin_excuse BOOLEAN DEFAULT 0,
        auto_nick_on_join BOOLEAN DEFAULT 0,
        enforce_suffix BOOLEAN DEFAULT 0,
        remove_suffix_on_role_loss BOOLEAN DEFAULT 0,
        suffix_format TEXT DEFAULT ' [𝙼𝚂𝚄𝚊𝚗]',
        present_channel_id INTEGER
    )''')
    
    # Ensure new columns exist on older databases
    c.execute("PRAGMA table_info('guild_configs')")
    existing_guild_columns = [row[1] for row in c.fetchall()]
    if 'present_channel_id' not in existing_guild_columns:
        c.execute("ALTER TABLE guild_configs ADD COLUMN present_channel_id INTEGER")

    # Attendance Records Table
    c.execute('''CREATE TABLE IF NOT EXISTS attendance_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        user_id INTEGER,
        status TEXT,
        timestamp TEXT,
        channel_id INTEGER,
        reason TEXT,
        FOREIGN KEY(guild_id) REFERENCES guild_configs(guild_id)
    )''')
    
    # Index for faster lookups
    c.execute('CREATE INDEX IF NOT EXISTS idx_records_guild_user ON attendance_records (guild_id, user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_records_guild_date ON attendance_records (guild_id, timestamp)')

    c.execute('''CREATE TABLE IF NOT EXISTS attendance_stats (
        guild_id INTEGER,
        user_id INTEGER,
        present_count INTEGER DEFAULT 0,
        absent_count INTEGER DEFAULT 0,
        excused_count INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, user_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS custom_commands (
        guild_id INTEGER,
        command_name TEXT,
        response_text TEXT NOT NULL,
        PRIMARY KEY (guild_id, command_name)
    )''')

    c.execute('CREATE INDEX IF NOT EXISTS idx_custom_commands_guild ON custom_commands (guild_id)')

    c.execute("PRAGMA table_info('attendance_stats')")
    existing_columns = [row[1] for row in c.fetchall()]
    if 'present_count' not in existing_columns:
        c.execute("ALTER TABLE attendance_stats ADD COLUMN present_count INTEGER DEFAULT 0")
    if 'absent_count' not in existing_columns:
        c.execute("ALTER TABLE attendance_stats ADD COLUMN absent_count INTEGER DEFAULT 0")
    if 'excused_count' not in existing_columns:
        c.execute("ALTER TABLE attendance_stats ADD COLUMN excused_count INTEGER DEFAULT 0")

    conn.commit()
    restore_snapshot_if_needed(conn)
    conn.close()
    logger.info("Database initialized at %s (snapshot: %s).", DB_FILE, SNAPSHOT_FILE)

def get_guild_config(guild_id):
    """Retrieves configuration for a guild."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM guild_configs WHERE guild_id = ?', (guild_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def update_guild_config(guild_id, **kwargs):
    """Updates specific fields in the guild configuration."""
    conn = get_connection()
    c = conn.cursor()
    
    # Check if exists
    c.execute('SELECT 1 FROM guild_configs WHERE guild_id = ?', (guild_id,))
    exists = c.fetchone()
    
    if not exists:
        # Create default entry first
        c.execute('INSERT INTO guild_configs (guild_id) VALUES (?)', (guild_id,))
    
    if kwargs:
        columns = ', '.join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [guild_id]
        c.execute(f'UPDATE guild_configs SET {columns} WHERE guild_id = ?', values)
    
    conn.commit()
    conn.close()
    write_snapshot()

def get_attendance_records(guild_id):
    """Retrieves all attendance records for a guild."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM attendance_records WHERE guild_id = ?', (guild_id,))
    rows = c.fetchall()
    conn.close()
    
    # Convert to dictionary format expected by bot {user_id: {status, timestamp, ...}}
    records = {}
    for row in rows:
        records[str(row['user_id'])] = {
            "status": row['status'],
            "timestamp": row['timestamp'],
            "channel_id": row['channel_id'],
            "reason": row['reason']
        }
    return records

def add_or_update_record(guild_id, user_id, status, timestamp, channel_id=None, reason=None):
    """Adds or updates an attendance record."""
    conn = get_connection()
    c = conn.cursor()
    
    # Upsert logic
    c.execute('''INSERT INTO attendance_records (guild_id, user_id, status, timestamp, channel_id, reason)
                 VALUES (?, ?, ?, ?, ?, ?)
                 ON CONFLICT(id) DO UPDATE SET
                 status=excluded.status,
                 timestamp=excluded.timestamp,
                 channel_id=excluded.channel_id,
                 reason=excluded.reason
    ''', (guild_id, user_id, status, timestamp, channel_id, reason))
    
    # Wait, SQLite UPSERT usually requires a unique constraint to conflict on.
    # We don't have a unique constraint on (guild_id, user_id) because we might want history?
    # But the current bot only stores ONE record per user per guild (current status).
    # So we should probably DELETE old record for this user or UPDATE it.
    
    # Let's clean up: Delete existing record for this user in this guild first
    # (Since we only track 'current' status in the JSON version)
    
    # Actually, let's use a unique constraint if we only want one record per user per day/session.
    # The JSON structure is `records: { "user_id": { ... } }`, so only one active record per user.
    
    conn.rollback() # Undo the insert above
    
    # Delete previous record for this user
    c.execute('DELETE FROM attendance_records WHERE guild_id = ? AND user_id = ?', (guild_id, user_id))
    
    # Insert new
    c.execute('''INSERT INTO attendance_records (guild_id, user_id, status, timestamp, channel_id, reason)
                 VALUES (?, ?, ?, ?, ?, ?)''', (guild_id, user_id, status, timestamp, channel_id, reason))
    
    conn.commit()
    conn.close()
    write_snapshot()

def replace_all_records(guild_id, records_dict):
    """Replaces all attendance records for a guild (bulk save)."""
    conn = get_connection()
    c = conn.cursor()
    
    # Transaction
    try:
        # Delete all existing
        c.execute('DELETE FROM attendance_records WHERE guild_id = ?', (guild_id,))
        
        # Insert new
        # records_dict is {user_id: {status, timestamp, channel_id, reason}}
        to_insert = []
        for uid, info in records_dict.items():
            to_insert.append((
                guild_id, 
                uid, 
                info.get('status', 'present'), 
                info.get('timestamp'), 
                info.get('channel_id'),
                info.get('reason')
            ))
            
        if to_insert:
            c.executemany('''INSERT INTO attendance_records (guild_id, user_id, status, timestamp, channel_id, reason)
                             VALUES (?, ?, ?, ?, ?, ?)''', to_insert)
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to replace records for guild {guild_id}: {e}")
        raise
    finally:
        conn.close()
    write_snapshot()

def clear_attendance_records(guild_id):
    """Clears all attendance records for a guild (e.g., reset)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM attendance_records WHERE guild_id = ?', (guild_id,))
    conn.commit()
    conn.close()
    write_snapshot()

def clear_attendance_stats(guild_id):
    """Clears all attendance stats (present/absent/excused counts) for a guild."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM attendance_stats WHERE guild_id = ?', (guild_id,))
    conn.commit()
    conn.close()
    write_snapshot()

def increment_status_count(guild_id, user_id, status, count=1):
    conn = get_connection()
    c = conn.cursor()
    present = 0
    absent = 0
    excused = 0
    if status == 'present':
        present = count
        column = 'present_count'
    elif status == 'absent':
        absent = count
        column = 'absent_count'
    elif status == 'excused':
        excused = count
        column = 'excused_count'
    else:
        conn.close()
        return
    c.execute(
        f'''INSERT INTO attendance_stats (guild_id, user_id, present_count, absent_count, excused_count)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET {column} = {column} + ?''',
        (guild_id, user_id, present, absent, excused, count)
    )
    conn.commit()
    conn.close()
    write_snapshot()

def get_attendance_leaderboard_count(guild_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) AS total FROM attendance_stats WHERE guild_id = ?', (guild_id,))
    row = c.fetchone()
    conn.close()
    return row['total'] if row else 0


def get_attendance_leaderboard(guild_id, limit=10, offset=0):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        '''SELECT user_id, present_count, absent_count, excused_count
           FROM attendance_stats
           WHERE guild_id = ?
           ORDER BY present_count DESC, user_id ASC
           LIMIT ? OFFSET ?''',
        (guild_id, limit, offset)
    )
    rows = c.fetchall()
    conn.close()
    return rows


def get_custom_commands(guild_id):
    """Returns all custom commands for a guild keyed by normalized command name."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        '''SELECT command_name, response_text
           FROM custom_commands
           WHERE guild_id = ?
           ORDER BY command_name ASC''',
        (guild_id,)
    )
    rows = c.fetchall()
    conn.close()
    return {row['command_name']: row['response_text'] for row in rows}


def get_custom_command(guild_id, command_name):
    """Returns the response text for one custom command."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        '''SELECT response_text
           FROM custom_commands
           WHERE guild_id = ? AND command_name = ?''',
        (guild_id, command_name)
    )
    row = c.fetchone()
    conn.close()
    return row['response_text'] if row else None


def upsert_custom_command(guild_id, command_name, response_text):
    """Creates or updates a custom command for a guild."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        '''INSERT INTO custom_commands (guild_id, command_name, response_text)
           VALUES (?, ?, ?)
           ON CONFLICT(guild_id, command_name) DO UPDATE SET
           response_text = excluded.response_text''',
        (guild_id, command_name, response_text)
    )
    conn.commit()
    conn.close()
    write_snapshot()


def delete_custom_command(guild_id, command_name):
    """Deletes a custom command and returns whether a row was removed."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        'DELETE FROM custom_commands WHERE guild_id = ? AND command_name = ?',
        (guild_id, command_name)
    )
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    if deleted:
        write_snapshot()
    return deleted
