-- Stocks
-- depends: bobux-20210606_01_7mvUl-real-estate-part-3

CREATE TABLE stock_holdings(
    ticker_symbol TEXT NOT NULL,
    owner_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    amount REAL NOT NULL DEFAULT 0.0,

    PRIMARY KEY(ticker_symbol, owner_id, guild_id)
);
