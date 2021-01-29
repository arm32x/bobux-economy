import sqlite3

connection = sqlite3.connect("bobux.db")

def initialize(cursor: sqlite3.Cursor):
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS guilds(
            id INTEGER NOT NULL PRIMARY KEY,
            prefix TEXT NOT NULL DEFAULT "b$"
        );
        CREATE TABLE IF NOT EXISTS members(
            id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            balance INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(id, guild_id),
            FOREIGN KEY(guild_id) REFERENCES guilds(id)
        );
    """)
    connection.commit()
