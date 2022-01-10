-- API keys
-- depends: bobux-20211013_01_wOzca-subscriptions  bobux-20211022_01_jVqfP-webhook-puppeting

CREATE TABLE api_keys(
    api_key_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,  -- The user this API key grants access to.
    guild_id INTEGER NOT NULL,
    access_level TEXT NOT NULL CHECK(access_level in ("read_only", "read_write")),
    label TEXT NOT NULL
);
