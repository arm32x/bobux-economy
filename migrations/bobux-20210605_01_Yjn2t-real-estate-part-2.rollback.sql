-- Real Estate Part 2
-- depends: bobux-20210604_01_KUMNT-real-estate

ALTER TABLE purchased_channels DROP COLUMN flagged_as_inactive;
ALTER TABLE guilds DROP COLUMN real_estate_category;
