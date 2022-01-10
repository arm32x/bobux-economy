import base64
from dataclasses import dataclass
from enum import Enum
import secrets
from typing import Dict, Optional, Tuple

import bcrypt
import discord

from bobux_economy.database import connection as db
from bobux_economy.globals import client

class ApiAccessLevel(Enum):
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"

@dataclass
class ApiKeyInfo:
    # noinspection PyUnresolvedReferences
    """
    Represents the information associated with an API key.

    Contains information associated with the API key, such as the member it
    grants access to, its access level, and the member who created it. Does not
    contain the API key itself.

    Attributes:
        member: The member this API key grants access to.
        access_level: Whether this API key grants read-only or read-write
            access to the member's account.
        label: A human-readable label associated with this API key to describe
            what the API key is intended to be used for.
        creator_id: The Discord ID of the user that created this API key. For
            all API keys granting access to normal users, this should be equal
            to the ID of the member.
    """
    member: discord.Member
    access_level: ApiAccessLevel
    label: str


def create(key_info: ApiKeyInfo) -> str:
    """
    Creates an API key and saves it to the database.

    Args:
        key_info: The information to associate with this API key.

    Returns:
        The generated API key, encoded in Base64.
    """

    api_key_bytes = secrets.token_bytes()
    api_key_hash: str = base64.b64encode(bcrypt.hashpw(api_key_bytes, bcrypt.gensalt())).decode("ascii")

    c = db.cursor()
    c.execute("""
        INSERT INTO api_keys(
            api_key_hash,
            user_id,
            guild_id,
            access_level,
            label
        ) VALUES(?, ?, ?, ?, ?);
    """, (
        api_key_hash,
        key_info.member.id,
        key_info.member.guild.id,
        key_info.access_level.value,
        key_info.label
    ))

    return base64.b64encode(api_key_bytes).decode("ascii")


async def get_info(api_key: str) -> Optional[ApiKeyInfo]:
    """
    Returns the information associated with the given API key, or None if the
    API key is invalid.

    Args:
        api_key: The API key to validate and get the information of.
    """

    api_key_bytes = base64.b64decode(api_key.encode("ascii"))
    c = db.cursor()
    c.execute("""
        SELECT api_key_hash FROM api_keys;
    """)
    for api_key_hash, in c.fetchall():
        if bcrypt.checkpw(api_key_bytes, base64.b64decode(api_key_hash.encode("ascii"))):
            c.execute("""
                SELECT user_id, guild_id, access_level, label
                    FROM api_keys WHERE api_key_hash = ?;
            """, (api_key_hash, ))
            row: Optional[Tuple[int, int, str, str]] = c.fetchone()

            if row is not None:
                user_id, guild_id, access_level_str, label = row
                access_level = ApiAccessLevel(access_level_str)

                guild = client.get_guild(guild_id) or await client.fetch_guild(guild_id)
                member = guild.get_member(user_id) or await guild.fetch_member(user_id)

                return ApiKeyInfo(member, access_level, label)

    return None


def list_(member: discord.Member) -> Dict[str, ApiKeyInfo]:
    c = db.cursor()
    c.execute("""
        SELECT api_key_hash, access_level, label
            FROM api_keys WHERE user_id = ? AND guild_id = ?;
    """, (member.id, member.guild.id))

    results = {}
    for api_key_hash, access_level_str, label in c.fetchall():
        results[api_key_hash] = ApiKeyInfo(
            member,
            ApiAccessLevel(access_level_str),
            label
        )
    return results


def revoke(member: discord.Member, api_key_hash: str) -> Optional[ApiKeyInfo]:
    c = db.cursor()
    c.execute("""
        SELECT access_level, label FROM api_keys
            WHERE user_id = ? AND guild_id = ? AND api_key_hash = ?;
    """, (member.id, member.guild.id, api_key_hash))
    row: Optional[Tuple[str, str]] = c.fetchone()

    if row is not None:
        access_level_str, label = row
        c.execute("""
            DELETE FROM api_keys WHERE api_key_hash = ?;
        """, (api_key_hash,))
        return ApiKeyInfo(
            member,
            ApiAccessLevel(access_level_str),
            label
        )
    else:
        return None
