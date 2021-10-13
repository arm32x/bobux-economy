-- Real Estate Archive Category
-- depends: bobux-20210921_01_ELDQa-slash-commands

ALTER TABLE guilds
    ADD COLUMN real_estate_archive_category INTEGER
    CHECK (real_estate_category IS NOT NULL OR real_estate_archive_category IS NULL);