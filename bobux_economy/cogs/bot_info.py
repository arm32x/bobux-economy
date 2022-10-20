"""
A cog that includes commands to check the current version of the bot and
view the changelog for the bot.
"""

import disnake
from disnake.ext import commands


class BotInfo(commands.Cog):
    bot: commands.InteractionBot
    changelog: str

    def __init__(self, bot: commands.InteractionBot):
        self.bot = bot

        with open("data/changelog.txt", "r") as changelog_file:
            self.changelog = changelog_file.read()


    @commands.slash_command(
        name="version",
        description="Check the version of the bot"
    )
    async def slash_version(self, ctx: disnake.ApplicationCommandInteraction):
        await ctx.send(self.changelog.strip().partition("\n")[0].strip(), ephemeral=True)

    @commands.slash_command(
        name="changelog",
        description="Show the changelog of the bot"
    )
    async def slash_changelog(self, ctx: disnake.ApplicationCommandInteraction):
        entries = self.changelog.strip().split("\n\n")
        page = ""
        for entry in entries:
            if len(page) + len(entry) + 8 > 1900:
                break
            else:
                page += f"\n\n{entry}"  # Yes, I know str.join(list) is faster
        await ctx.send(f"```{page}```\nFull changelog at <https://github.com/arm32x/bobux-economy/blob/master/bobux_economy/data/changelog.txt>", ephemeral=True)


def setup(bot: commands.InteractionBot):
    bot.add_cog(BotInfo(bot))
