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
import factions 
import gsheets
import gspread
from google.oauth2.service_account import Credentials



client = commands.Bot(command_prefix=">", intents=discord.Intents.all())

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def sort_sheet():
    data = worksheet.get_all_records()
    data.sort(key=lambda x: x['KPH'], reverse=True)
    worksheet.clear()
    worksheet.append_row(['Index', 'Username', 'KPH', 'Nationality', 'Factions', 'Status'])
    for i, row in enumerate(data, start=1):
        row['Index'] = i
        worksheet.append_row(list(row.values()))

creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
gs_client = gspread.authorize(creds)
spreadsheet = gs_client.open('KPH Leaderboard Datasets')
worksheet = spreadsheet.worksheet('Sheet1')

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
    2: "Eagles of Illyria",
    3: "83rd Deathkorps of Krieg",
    4: "41st Strosstruppen Brigade",
    5: "The White Legion",
    6: "Confederacion Iberio-Americana",
    7: "Imperial Federation of R",
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
async def new_submission(interaction: discord.Interaction, username: str, faction: str, nationality: str, kph: int, image: str):
    await interaction.response.send_message("Please confirm that the submission is correct. Type `yes` to confirm or `no` to cancel.")

    def check(message):
        return message.author == interaction.user and message.channel == interaction.channel

    msg = await client.wait_for("message", check=check)
    if msg.content.lower() == "yes":
        await interaction.followup.send(f"**[ :new: >New Submission< :new: ]**, \nUser: **{username}** \nFaction: **{faction}** \nNationality: **{nationality}** \nKPH: **{kph}** \n**[Image]({image})** ")
        # Google Sheets Functions #
        status = "[ :new: ]"
        row = [username, kph, nationality, faction, status]
        worksheet.append_row(row, table_range="H:M")
    else:
        await interaction.followup.send("Submission cancelled.")
    

@client.tree.command(name="update", description="Updating existing stats for the leaderboard")
@app_commands.describe(username="E.g, IAmHeating > IAmGay", faction=" E.g, 41st > DK", nationality="Nationality of their country origin (optional)", kph=" E.g, 127 > 135", image="Use the link of what they shared")   
@app_commands.check(lambda interaction: interaction.user.get_role(1104697514793369671) is not None or interaction.user.guild_permissions.administrator)
async def update_submission(interaction: discord.Interaction, username: str, faction: str = "", nationality: str = "", kph: str = "", image: str = ""): 
    await interaction.response.send_message("Please confirm that the submission is correct. Type `yes` to confirm or `no` to cancel.")

    def check(message):
        return message.author == interaction.user and message.channel == interaction.channel

    msg = await client.wait_for("message", check=check)
    if msg.content.lower() == "yes":
        faction_str = f"Faction: **{faction}**" if faction else ""
        nationality_str = f"Nationality: **{nationality}**" if nationality else ""
        kph_str = f"KPH: **{kph}**" if kph else ""
        image_str = f"Image: **{image}**" if image else ""
        emoji = discord.PartialEmoji(name="emoji_name", id=1215496391506264115, animated=False)
        await interaction.followup.send(f"**[ {emoji} >Update Submission< {emoji} ]** \nUsername: **{username}** \n{faction_str} \n{nationality_str} \n{kph_str} \n{image_str}")
        # Google Sheets Functions #
        status = "[ <:ups:1215496391506264115> ]"
        row = [username, kph, nationality, faction, status]
        worksheet.append_row(row, table_range="H:M") 
    else:
        await interaction.followup.send("Submission cancelled.")
   

@client.tree.command(name="update_stats", description="Update existing stats for the leaderboard")
@app_commands.describe(username="Username of the player", kph="New KPH value", faction="New faction value", nationality="New nationality value", status="New status value")
@app_commands.check(lambda interaction: interaction.user.get_role(1104697514793369671) is not None or interaction.user.guild_permissions.administrator)
async def update_stats(interaction: discord.Interaction):
    gsheet = gsheets.sheets
    
    username = spreadsheet.get_worksheet(8)
    kph = spreadsheet.get_worksheet(9)
    nationality = spreadsheet.get_worksheet(10)
    faction = spreadsheet.get_worksheet(11)
    status = spreadsheet.get_worksheet(12)

    cell = username.find(username, in_column="H")
    
    if cell:
        row_number = cell.row
        
        # Update columns A to F for the found row using data from columns G to M
        gsheet.update_cell(row_number, 1, row_number - 1)     # Column A (Index)
        gsheet.update_cell(row_number, 2, username)          # Column B (Username)
        gsheet.update_cell(row_number, 3, kph)               # Column C (New KPH value)
        gsheet.update_cell(row_number, 4, nationality)       # Column D (New nationality value)
        gsheet.update_cell(row_number, 5, faction)           # Column E (New faction value)
        gsheet.update_cell(row_number, 6, status)            # Column F (New status value)
        
        # Sort the sheet based on KPH value (Column C) in descending order
        gsheet.sort((3, 'descending'))
        
        await interaction.response.send_message("Leaderboard in Google Sheets have been updated")




def main() -> None:
    client.run(token=TOKEN)

if __name__ == '__main__':
    main()