-- Better config
-- depends: bobux-20211013_01_wOzca-subscriptions  bobux-20211022_01_jVqfP-webhook-puppeting

CREATE TABLE
    guild_config (
        snowflake INTEGER NOT NULL PRIMARY KEY,
        admin_role_id INTEGER,
        memes_channel_id INTEGER,
        real_estate_category_id INTEGER
    );

INSERT INTO
    guild_config
SELECT
    id,
    admin_role,
    memes_channel,
    real_estate_category
FROM
    guilds;
