from datetime import datetime, timedelta, timezone
from json.decoder import JSONDecodeError
import math
from typing import *

import pandas
import discord
from discord.ext import commands
from yahoo_fin import stock_info

import balance
from database import connection as db


SYMBOL_FORMATS = [ "{}-USD", "{}", "^{}", "{}=F", "{}USD=X" ]

def _get_price_internal(ticker_symbol: str) -> Optional[float]:
    try:
        price = stock_info.get_live_price(ticker_symbol)
        if math.isnan(price):
            return None
        else:
            return price
    # The get_live_price() function throws so many different errors...
    except (AssertionError, KeyError, JSONDecodeError):
        return None

def get_price(ticker_symbol: str) -> Optional[float]:
    ticker_symbol = ticker_symbol.upper()
    for symbol_format in SYMBOL_FORMATS:
        price = _get_price_internal(symbol_format.format(ticker_symbol))
        if price is not None:
            return price
    return None


def _get_data_internal(ticker_symbol: str) -> Optional[pandas.DataFrame]:
    try:
        dataframe = stock_info.get_data(ticker_symbol, start_date=(datetime.now(tz=timezone.utc) - timedelta(days=5)), interval="1m")
        return dataframe
    except (AssertionError, KeyError, JSONDecodeError):
        return None

def _get_data(ticker_symbol: str) -> Optional[pandas.DataFrame]:
    ticker_symbol = ticker_symbol.upper()
    for symbol_format in SYMBOL_FORMATS:
        dataframe = _get_data_internal(symbol_format.format(ticker_symbol))
        if dataframe is not None:
            return dataframe
    return None

def get_price_history(ticker_symbol: str) -> Optional[List[float]]:
    dataframe = _get_data(ticker_symbol)
    if dataframe is None:
        return None
    else:
        return list(dataframe["close"][-80 * 15::15])


def get(member: discord.Member, ticker_symbol: str) -> float:
    c = db.cursor()
    ticker_symbol = ticker_symbol.upper()
    c.execute("""
        SELECT amount FROM stock_holdings WHERE ticker_symbol = ? AND owner_id = ? AND guild_id = ?;
    """, (ticker_symbol, member.id, member.guild.id))
    return (c.fetchone() or (None, ))[0] or 0.0

def get_all(member: discord.Member) -> Dict[str, float]:
    c = db.cursor()
    c.execute("""
            SELECT ticker_symbol, amount FROM stock_holdings WHERE owner_id = ? AND guild_id = ?;
        """, (member.id, member.guild.id))
    results: List[Tuple[str, float]] = c.fetchall()
    return dict(results)

def set(member: discord.Member, ticker_symbol: str, units: float):
    ticker_symbol = ticker_symbol.upper()
    c = db.cursor()
    if units == 0.0:
        c.execute("""
            DELETE FROM stock_holdings WHERE ticker_symbol = ? AND owner_id = ? AND guild_id = ?;
        """, (ticker_symbol, member.id, member.guild.id))
    else:
        c.execute("""
            INSERT INTO stock_holdings(ticker_symbol, owner_id, guild_id, amount) VALUES(?, ?, ?, ?)
                ON CONFLICT(ticker_symbol, owner_id, guild_id) DO UPDATE SET amount = excluded.amount;
        """, (ticker_symbol, member.id, member.guild.id, units))
    db.commit()


def add(member: discord.Member, ticker_symbol: str, units: float):
    if units < 0.0:
        raise balance.NegativeAmountError()

    current_amount = get(member, ticker_symbol)
    set(member, ticker_symbol, current_amount + units)

def subtract(member: discord.Member, ticker_symbol: str, units: float, allow_overdraft: bool = False):
    if units < 0.0:
        raise balance.NegativeAmountError()

    current_amount = get(member, ticker_symbol)

    if not allow_overdraft and current_amount < units:
        raise commands.CommandError(f"Insufficient holdings in '{ticker_symbol.upper()}'.")

    set(member, ticker_symbol, current_amount - units)


def buy(buyer: discord.Member, ticker_symbol: str, units_or_total_price: Union[float, Tuple[int, bool]]) -> Tuple[float, Tuple[int, bool]]:
    ticker_symbol = ticker_symbol.upper()

    price_per_unit = get_price(ticker_symbol)
    if price_per_unit is None:
        raise commands.CommandError(f"Ticker symbol '{ticker_symbol}' does not exist.")

    if isinstance(units_or_total_price, float):
        units = units_or_total_price
        total_price = price_per_unit * units_or_total_price
    elif isinstance(units_or_total_price, tuple):
        amount_float = balance.to_float(*units_or_total_price)
        units = amount_float / price_per_unit
        total_price = amount_float
    else:
        raise TypeError("Amount must be either float or (int, bool).")

    balance.subtract(buyer, *balance.from_float_round(total_price))
    add(buyer, ticker_symbol, units)

    return units, balance.from_float_ceil(total_price)

def sell(seller: discord.Member, ticker_symbol: str, units_or_total_price: Optional[Union[float, Tuple[int, bool]]]) -> Tuple[float, Tuple[int, bool]]:
    ticker_symbol = ticker_symbol.upper()

    price_per_unit = get_price(ticker_symbol)
    if price_per_unit is None:
        raise commands.CommandError(f"Ticker symbol '{ticker_symbol}' does not exist.")

    if units_or_total_price is None:
        units_or_total_price = get(seller, ticker_symbol)

    if isinstance(units_or_total_price, float):
        units = units_or_total_price
        total_price = price_per_unit * units_or_total_price
    elif isinstance(units_or_total_price, tuple):
        amount_float = balance.to_float(*units_or_total_price)
        units = amount_float / price_per_unit
        total_price = amount_float
    else:
        raise TypeError("Amount must be either float or (int, bool).")

    subtract(seller, ticker_symbol, units)
    balance.add(seller, *balance.from_float_round(total_price))

    return units, balance.from_float_round(total_price)


def to_string(ticker_symbol: str, units: float) -> str:
    ticker_symbol = ticker_symbol.upper()

    price_per_unit = get_price(ticker_symbol)
    if price_per_unit is None:
        return f"{units} {ticker_symbol}"

    value_in_bobux = balance.from_float_round(price_per_unit * units)

    return f"{units} {ticker_symbol} (worth {balance.to_string(*value_in_bobux)})"

def validate_ticker_symbol(ticker_symbol: Optional[str]):
    if ticker_symbol is not None and not ticker_symbol.isalpha():
        raise commands.CommandError(f"Invalid ticker symbol '{ticker_symbol.upper()}'.")
