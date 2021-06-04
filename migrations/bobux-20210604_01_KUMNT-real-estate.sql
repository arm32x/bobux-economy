-- Real Estate
-- depends: bobux-20210419_01_ODHrt-create-tables-from-0-2-0

CREATE TABLE purchased_channels(
    id INTEGER PRIMARY KEY,
    owner_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    purchase_time INTEGER NOT NULL,
    last_post_time INTEGER
);
