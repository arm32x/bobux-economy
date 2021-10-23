-- Webhook puppeting
-- depends: bobux-20210921_01_ELDQa-slash-commands

-- Intended to be an append-only log. Rows should not be deleted when webhooks
-- are deleted because messages sent by those webhooks stick around forever.
CREATE TABLE webhooks(
    webhook_id INTEGER PRIMARY KEY,
    member_id INTEGER NOT NULL
);