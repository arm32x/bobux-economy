-- Add config for upvote and downvote emojis
-- depends: bobux-20210419_01_ODHrt-create-tables-from-0-2-0

ALTER TABLE guilds DROP COLUMN upvote_emoji;
ALTER TABLE guilds DROP COLUMN downvote_emoji;