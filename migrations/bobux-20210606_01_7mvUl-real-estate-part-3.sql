-- Real Estate Part 3
-- depends: bobux-20210605_01_Yjn2t-real-estate-part-2

-- This assumes there are no rows in this table.
DROP TABLE purchased_channels;

CREATE TABLE purchased_channels(
    id INTEGER PRIMARY KEY,
    owner_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    purchase_time timestamp NOT NULL,
    last_post_time timestamp,
    flagged_as_inactive INTEGER NOT NULL CHECK(flagged_as_inactive IN (0, 1)) DEFAULT 0
);
