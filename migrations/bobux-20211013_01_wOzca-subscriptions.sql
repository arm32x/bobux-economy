-- Subscriptions
-- depends: bobux-20210921_01_ELDQa-slash-commands

CREATE TABLE available_subscriptions(
    role_id INTEGER PRIMARY KEY,
    guild_id INTEGER NOT NULL,
    price INTEGER NOT NULL,  -- Charged weekly
    spare_change BOOLEAN NOT NULL CHECK(spare_change IN (0, 1))
);

CREATE TABLE member_subscriptions(
    member_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    subscribed_since timestamp NOT NULL,
    PRIMARY KEY(member_id, role_id),

    -- SQLite does not honor foreign keys by default, but I will add them anyway
    FOREIGN KEY(member_id) REFERENCES members(id),
    FOREIGN KEY(role_id) REFERENCES available_subscriptions(role_id)
);