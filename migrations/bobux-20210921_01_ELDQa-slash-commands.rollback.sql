-- Slash commands
-- depends: bobux-20210620_01_pFgdS-stocks

-- Can't use DROP COLUMN since target SQLite version is 3.27
ALTER TABLE guilds RENAME TO guilds_old;
CREATE TABLE guilds(
    -- From "Create tables from 0.2.0"
    id INTEGER NOT NULL PRIMARY KEY,
    prefix TEXT NOT NULL DEFAULT "b$",
    admin_role INTEGER,
    memes_channel INTEGER,
    last_memes_message INTEGER,
    -- From "Real Estate Part 2"
    real_estate_category INTEGER
);
INSERT INTO guilds SELECT id, admin_role, memes_channel, last_memes_message, real_estate_category FROM guilds_old;
DROP TABLE guilds_old;
