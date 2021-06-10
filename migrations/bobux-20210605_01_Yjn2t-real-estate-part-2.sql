-- Real Estate Part 2
-- depends: bobux-20210604_01_KUMNT-real-estate

ALTER TABLE purchased_channels ADD COLUMN
    flagged_as_inactive INTEGER NOT NULL CHECK(flagged_as_inactive IN (0, 1)) DEFAULT 0;

ALTER TABLE guilds ADD COLUMN
    real_estate_category INTEGER;