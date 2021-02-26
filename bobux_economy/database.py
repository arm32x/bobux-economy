import sqlite3

connection = sqlite3.connect("bobux.db")

def initialize(cursor: sqlite3.Cursor):
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS guilds(
            id INTEGER NOT NULL PRIMARY KEY,
            prefix TEXT NOT NULL DEFAULT "b$",
            admin_role INTEGER,
            memes_channel INTEGER,
            last_memes_message INTEGER
        );
        CREATE TABLE IF NOT EXISTS members(
            id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            balance INTEGER NOT NULL DEFAULT 0 CHECK(balance >= 0),
            spare_change BOOLEAN NOT NULL DEFAULT 0 CHECK(spare_change IN (0, 1)),
            
            PRIMARY KEY(id, guild_id),
            FOREIGN KEY(guild_id) REFERENCES guilds(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS votes(
            message_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            member_id INTEGER NOT NULL,
            vote INTEGER NOT NULL CHECK(vote IN (-1, 1)),
            
            PRIMARY KEY(message_id, member_id),
            FOREIGN KEY(member_id) REFERENCES members(id) ON DELETE CASCADE
        );
    """)
    connection.commit()
