-- Multiple vote channels
-- depends: bobux-20230709_01_xzknm-better-config

CREATE TABLE
    guild_config_vote_channel_ids (
        snowflake INTEGER NOT NULL,
        value INTEGER NOT NULL,
        PRIMARY KEY (snowflake, value)
    );

INSERT INTO
    guild_config_vote_channel_ids
SELECT
    snowflake,
    memes_channel_id
FROM
    guild_config
WHERE
    memes_channel_id IS NOT NULL;

ALTER TABLE guild_config
DROP COLUMN memes_channel_id;
