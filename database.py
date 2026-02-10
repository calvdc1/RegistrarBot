import os
import sqlite3
import json
import logging
from datetime import datetime

# Use environment variable for DB location (default to local file)
DB_FILE = os.getenv("DB_FILE", "attendance.db")
logger = logging.getLogger(__name__)

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
        suffix_format TEXT DEFAULT ' [𝙼𝚂𝚄𝚊𝚗]'
    )''')
    
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

    conn.commit()
    conn.close()
    logger.info("Database initialized.")

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

def clear_attendance_records(guild_id):
    """Clears all attendance records for a guild (e.g., reset)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM attendance_records WHERE guild_id = ?', (guild_id,))
    conn.commit()
    conn.close()
