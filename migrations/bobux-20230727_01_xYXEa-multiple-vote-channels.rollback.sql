-- Multiple vote channels
-- depends: bobux-20230709_01_xzknm-better-config

ALTER TABLE guild_config
ADD COLUMN memes_channel_id INTEGER;

DROP TABLE guild_vote_channel_ids;
