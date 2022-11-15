import disnake
from disnake.ui import ActionRow, MessageUIComponent


async def wait_for_component(
    client: disnake.Client, action_row: ActionRow[MessageUIComponent]
) -> disnake.MessageInteraction:
    """
    Waits for a component interaction. Only accepts interactions based
    on the custom ID of the component.

    Adapted from the implementation in interactions.py legacy-v3.
    """

    custom_ids = [c.custom_id for c in action_row.children if c.custom_id is not None]

    def _check(ctx: disnake.MessageInteraction):
        return ctx.data.custom_id in custom_ids

    return await client.wait_for("message_interaction", check=_check)
