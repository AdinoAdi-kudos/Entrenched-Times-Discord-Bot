from typing import Final
import discord
import os
from dotenv import load_dotenv
from discord import Intents, Message
from responses import get_response
from discord import app_commands
from discord.ext import commands
from discord import Interaction
from discord.ui import Select, View, Modal, TextInput
import factions as d


client = commands.Bot(command_prefix=">", intents=discord.Intents.all())
#===================#
# Discord Bot response
#==================#

load_dotenv()
TOKEN: Final[str] = os.getenv('DISCORD_TOKEN') 

intents: Intents = Intents.default()
intents.message_content = True


@client.event
async def on_ready() -> None:
    print(f'{client.user} is now running!')
    await client.tree.sync()

# async def send_message(message: Message, user_message: str) -> None:
#     if not user_message:
#         print('(Message was empty because intents were not enabled probably)')
#         return

#     is_private = user_message[0] == '?'
#     if is_private:
#         user_message = user_message[1:]
#     try:
#         response: str = get_response(user_message)
#         await (message.author.send(response) if is_private else message.channel.send(response))
#     except Exception as e:
#         print(e)

# @client.event
# async def on_message(message: Message) -> None:
#     if message.author == client.user:
#         return
    
#     username: str = str(message.author)
#     user_message: str = message.content
#     channel: str = str(message.channel)

#     print(f'[{channel}] {username}: "{user_message}"')
#     await send_message(message, user_message)

#============================#
# Discord Bot Menu Interactions
#============================#

class Menu(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None

        

@client.tree.command(name="hello", description="Why is this bot created?")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(f"Hey {interaction.user.mention}! This bot is developed for the sole purpose in simplifying the process of managing the workload for the Entrenched Times staff, any inquiry about the bot. Please stop, just don't. \n This bot has some uses if you guys are so desperate about it. Use /help commands to see which commands can you use")

@client.tree.command(name="help", description="Shows list of commands & who has perms")
async def help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="List of commands",
        description="Here are some list",
        color=discord.Color.dark_green()
    )
    embed.add_field(name="/context", value="Literally context about the existence of this bot", inline=False)
    embed.add_field(name="/faction", value="Public domain info for each factions, WIP", inline=False)
    embed.add_field(name="/submission", value="Sumbitting KPH for the leaderboard, only accessible by Yelp Reviewer and Admins", inline=False)
    embed.add_field(name="/update", value="Updating existing user for the leaderboard, only accessible by Yelp Reviewer and Admins", inline=False)

    embed.set_footer(text="Powered by Entrenched Times staff")

    await interaction.response.send_message(embed=embed, ephemeral=True)

faction_names = {
    1: "Entrenched Times",
    2: "Illyria",
    3: "DK",
    4: "41st",
    5: "TWL",
    6: "CIA",
}

@client.tree.command(name="faction", description="Explain what are these factions")
@app_commands.describe(faction="Choose a faction")
@app_commands.choices(faction=[
        app_commands.Choice(name='ET', value=1),
        app_commands.Choice(name='Illyria', value=2),
        app_commands.Choice(name="DK", value=3),
        app_commands.Choice(name="41st", value=4),
        app_commands.Choice(name="TWL", value=5),
        app_commands.Choice(name="CIA", value=6),
        app_commands.Choice(name="IFR", value=7),
    ])
async def list(interaction: discord.Interaction, faction: int):
    from factions import cruncher
    faction_name = faction_names[faction]
    await cruncher(interaction, faction_name)


#============================#
# Discord Entrenched Staff Wok
#============================#


@client.tree.command(name="submission", description="KPH submission for the leaderboard")
@app_commands.describe(username="Username of the player", faction="Faction of the user", nationality="Nationality of their country origin", kph="Their KPH based on the image", image="Use the link of what they shared")
@app_commands.check(lambda interaction: interaction.user.get_role(1104697514793369671) is not None or interaction.user.guild_permissions.administrator)
async def new_submission(interaction: discord.Interaction, username: str, faction: str, nationality: str, kph: int, image: str ):
    await interaction.response.send_message("Please confirm that the submission is correct. Type `yes` to confirm or `no` to cancel.")

    def check(message):
        return message.author == interaction.user and message.channel == interaction.channel

    msg = await client.wait_for("message", check=check)
    if msg.content.lower() == "yes":
        await interaction.followup.send(f"**[ :new: >New Submission< :new: ]**, \nUser: **{username}** \nFaction: **{faction}** \nNationality: **{nationality}** \nKPH: **{kph}** \n**[Image]({image})** ")
    else:
        await interaction.followup.send("Submission cancelled.")

@client.tree.command(name="update", description="Updating existing stats for the leaderboard")
@app_commands.describe(username="E.g, IAmHeating > IAmGay", faction=" E.g, 41st > DK", nationality="Nationality of their country origin (optional)", kph=" E.g, 127 > 135", image="Use the link of what they shared")
@app_commands.check(lambda interaction: interaction.user.get_role(1104697514793369671) is not None or interaction.user.guild_permissions.administrator)
async def update_submission(interaction: discord.Interaction, username: str, faction: str = "", nationality: str = "", kph: int = 0, image: str = ""):
    await interaction.response.send_message("Please confirm that the submission is correct. Type `yes` to confirm or `no` to cancel.")

    def check(message):
        return message.author == interaction.user and message.channel == interaction.channel

    msg = await client.wait_for("message", check=check)
    if msg.content.lower() == "yes":
        faction_str = f"Faction: **{faction}**" if faction else ""
        nationality_str = f"Nationality: **{nationality}**" if nationality else ""
        kph_str = f"KPH: **{kph}**" if kph else ""
        image_str = f"Image: **{image}**" if image else ""
        await interaction.followup.send(f"**[ :new: >New Submission< :new: ]** \nUsername: **{username}** \n{faction_str} \n{nationality_str} \n{kph_str} \n{image_str}")
    else:
        await interaction.followup.send("Submission cancelled.")

def main() -> None:
    client.run(token=TOKEN)

if __name__ == '__main__':
    main()