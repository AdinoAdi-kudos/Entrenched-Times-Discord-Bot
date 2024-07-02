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
import gspread
from google.oauth2.service_account import Credentials
import asyncio
import time
import random
import difflib



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
log_sheet = spreadsheet.worksheet('Sheet2')

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
# 
#     is_private = user_message.lower().startswith('et') or user_message.lower() == 'entrenched times'
#     if is_private:
#         user_message = user_message[2:].strip()  # Remove 'ET' or 'Entrenched Times' from the start of the message
#     try:
#         response: str = get_response(user_message)
#         await (message.author.send(response) if is_private else message.channel.send(response))
#     except Exception as e:
#         print(e)
# 
# @client.event
# async def on_message(message: Message) -> None:
#     if message.author == client.user:
#         return
# 
#     username: str = str(message.author)
#     user_message: str = message.content
#     channel: str = str(message.channel)
# 
#     print(f'[{channel}] {username}: "{user_message}"')
#     await send_message(message, user_message)


#============================#
# Discord Bot Menu Interactions
#============================#

class Menu(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None

def get_intro_message() -> str:
    return '''
    Welcome to Entrenched Times! 📰

    Hello there! I'm your friendly neighborhood bot here at Entrenched Times, your go-to hub for news and community interaction. 🌟 Whether you're looking for the latest updates, eager to climb the leaderboard, or excited to share your incredible fanart and creations, you're in the right place!

    Here's what I can help you with:

    📅 Up-to-date News: Stay informed with the latest headlines and updates from our diverse faction communities. [Here is the link channel for mainstream news;](https://discord.com/channels/1038679606498181190/1038706213875093546)

    🏆 Leaderboard: Track your progress and see where you stand among your peers. [Here is the link channel for leaderboard;](https://discord.com/channels/1038679606498181190/1210536992513855529)

    🎨 Community Creations: Share and showcase your creative works and fanart with fellow members. [Here is the link channel for the community creations;](https://discord.com/channels/1038679606498181190/1183471479791296532)

    🔍 Interactivity: Don'tt ask me anything! I'm here just to run the workload by the Entrenched Times staff but you can ask any people in the server for help.

    Get started by exploring our channels and joining the conversation. We're thrilled to have you here at Entrenched Times! [For more information, check out this channel;](https://discord.com/channels/1038679606498181190/1104407115130486825)

    Powered by your enthusiasm and our commitment to community excellence. 🚀
    '''.strip()

@client.event
async def on_member_join(member: discord.Member):
    intro_message = get_intro_message()
    try:
        await member.send(intro_message)
    except discord.Forbidden:
        print(f"❌ Failed to send intro message to {member.display_name}. DMs are disabled.")

@client.tree.command(name="context", description="Why is this bot created?")
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
    embed.add_field(name="/update_stats", value="Updating the pending stats made by /submission or /update in the Google Sheets. Only accessible by Yelp Reviewer and Admins", inline=False)

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
async def faction_list(interaction: discord.Interaction, faction: int):
    from factions import cruncher
    faction_name = faction_names[faction]
    await cruncher(interaction, faction_name)


#============================#
# Discord Entrenched Staff Wok
#============================#


@client.tree.command(name="submission", description="KPH submission for the leaderboard")
@app_commands.describe(username="Username of the player", faction="Faction of the user", nationality="Nationality of their country origin", kph="Their KPH based on the image", image="Use the link of what they shared")
@app_commands.check(lambda interaction: interaction.user.get_role(1104697514793369671) is not None or interaction.user.guild_permissions.administrator)
async def new_submission(interaction: discord.Interaction, username: str, faction: str, nationality: str, kph: float, image: str):
    await interaction.response.send_message("Please confirm that the submission is correct. Type `yes` to confirm or `no` to cancel.")

    def check(message):
        return message.author == interaction.user and message.channel == interaction.channel

    msg = await client.wait_for("message", check=check)
    if msg.content.lower() == "yes":
        await interaction.followup.send(f"**[ :new: >New Submission< :new: ]**, \nUser: **{username}** \nFaction: **{faction}** \nNationality: **{nationality}** \nKPH: **{kph}** \n**[Image]({image})** ")

        # Google Sheets Functions #
        main_table = worksheet.get_all_records(expected_headers=["Index", "Username", "KPH", "Nationality", "Factions", "Status"])
        new_submission = True
        for row in main_table:
            if row["Username"] == username:
                new_submission = False
                row["KPH"] = kph
                row["Nationality"] = nationality
                row["Factions"] = faction
                row["Status"] = "[ :new: ]"
                break

        if new_submission:
            next_index = len(main_table) + 1
            worksheet.update_cell(next_index + 1, 1, next_index)
            worksheet.update_cell(next_index + 1, 2, username)
            worksheet.update_cell(next_index + 1, 3, kph)
            worksheet.update_cell(next_index + 1, 4, nationality)
            worksheet.update_cell(next_index + 1, 5, faction)
            worksheet.update_cell(next_index + 1, 6, "[ :new: ]")

        # Logging
        # Logging
            log_spreadsheet = spreadsheet
            log_sheet = log_spreadsheet.worksheet("Sheet2") 
            log_sheet.append_row([username, "", "", "", "", "", "", "","New Submission"])
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
        # Google Sheets Functions #
        main_table = worksheet.get_all_records(expected_headers=["Index", "Username", "KPH", "Nationality", "Factions", "Status"])
        usernames = [row['Username'] for row in main_table]
        if username in usernames:
            row_index = usernames.index(username) + 2
            old_username = username
        else:
            close_matches = difflib.get_close_matches(username, usernames, n=1, cutoff=0.6)
            if close_matches:
                close_match = close_matches[0]
                row_index = usernames.index(close_match) + 2
                old_username = close_match
            else:
                await interaction.followup.send("Username not found in main table.")
                return

        old_kph = worksheet.cell(row_index, 3).value
        old_faction = worksheet.cell(row_index, 5).value
        old_nation = worksheet.cell(row_index, 4).value

        faction_str = f"Faction: **{faction}**" if faction and faction!= old_faction else ""
        nationality_str = f"Nationality: **{nationality}**" if nationality and nationality!= old_nation else ""
        kph_str = f"KPH: **{kph}**" if kph and kph!= old_kph else ""
        image_str = f"Image: **{image}**" if image else ""
        emoji = discord.PartialEmoji(name="emoji_name", id=1215496391506264115, animated=False)
        await interaction.followup.send(f"**[ {emoji} >Update Submission< {emoji} ]** \nUsername: **{username}** \n{faction_str} \n{nationality_str} \n{kph_str} \n{image_str}")

        if kph:
            worksheet.update_cell(row_index, 3, kph)
            new_kph = kph
        else:
            new_kph = old_kph
        if faction:
            worksheet.update_cell(row_index, 5, faction)
            new_faction = faction
        else:
            new_faction = old_faction
        if nationality:
            worksheet.update_cell(row_index, 4, nationality)
            new_nation = nationality
        else:
            new_nation = old_nation
        worksheet.update_cell(row_index, 6, "[ <:ups:1215496391506264115> ]")

        # Logging
        log_sheet.append_row([old_username, username, old_kph, new_kph, old_faction, new_faction, old_nation, new_nation, "Updated Submission"])
    else:
        await interaction.followup.send("Submission cancelled.")

@client.tree.command(name="update_stats", description="Update existing stats for the leaderboard")
@app_commands.check(lambda interaction: interaction.user.get_role(1104697514793369671) is not None or interaction.user.guild_permissions.administrator)
async def update_stats(interaction: discord.Interaction):
    await interaction.response.defer()

    asyncio.create_task(update_stats_background(interaction))
async def update_stats_background(interaction: discord.Interaction):
    if interaction.response.is_done():
        await interaction.channel.send("Leaderboard in Google Sheets is being updated...")
    else:
        await interaction.response.defer()
    gc = gspread.service_account(filename='credentials.json')
    spreadsheet = gc.open('KPH Leaderboard Datasets')
    worksheet = spreadsheet.sheet1  

    all_records = worksheet.get_all_records(expected_headers=["Index", "Username", "KPH", "Nationality", "Factions", "Status"])

    usernames = [record['Username'] for record in all_records]
    kphs = [record['KPH'] for record in all_records]
    nationalities = [record['Nationality'] for record in all_records]
    factions = [record['Factions'] for record in all_records]
    statuses = [record['Status'] for record in all_records]

    new_data = [{'Username': username, 'KPH': kph, 'Nationality': nationality, 'Factions': faction, 'Status': status} for username, kph, nationality, faction, status in zip(usernames, kphs, nationalities, factions, statuses)]
    combined_data = new_data
    combined_data.sort(key=lambda x: float(x['KPH']) if x['KPH'] else 0, reverse=True)

    header = [['Index', 'Username', 'KPH', 'Nationality', 'Factions', 'Status']]
    data = [[index, x['Username'], x['KPH'], x['Nationality'], x['Factions'], x['Status']] for index, x in enumerate(combined_data, start=1)]

    # Clear the contents of the worksheet
    worksheet.batch_update([{
        'range': 'A1:F' + str(len(data) + 1),
        'values': [[''] * len(header[0])] * (len(data) + 1)
    }])

    retry_delay = 1
    max_retries = 5

    for attempt in range(max_retries):
        try:
            worksheet.update('A1:F' + str(len(data) + 1), [header[0]] + data)  #Update entire range, including header
            break
        except gspread.exceptions.APIError as e:
            if e.resp.status == 429:
                print(f"Rate limit exceeded. Waiting {retry_delay} seconds before retrying.")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            else:
                raise
    else:
        print("Failed to update sheet after max retries.")

    # Update the status column with the saved values
    worksheet.update('F2:F' + str(len(statuses) + 1), [[status] for status in statuses])

    if interaction.response.is_done():
        await interaction.channel.send("**Leaderboard in Google Sheets is done being updated!**")
    else:
        await interaction.response.defer()

@client.tree.command(name="leaderboard", description="Update existing stats for the leaderboard")
@app_commands.check(lambda interaction: interaction.user.get_role(1104697514793369671) is not None or interaction.user.guild_permissions.administrator)
async def update_stats(interaction: discord.Interaction):
    await interaction.response.defer()

    data = worksheet.get_all_records(expected_headers=["Index", "Username", "KPH", "Nationality", "Factions", "Status"])
    log_data = log_sheet.get_all_records()

    messages = []
    message = "# KPH Leaderboard\n### (Must be from an account with 24 hours or more, and over 100 kph.)\n"

    for i, row in enumerate(data, start=1):
        if i <= 3:
            medal = ["🥇", "🥈", "🥉"][i-1]
        else:
            medal = f"<:4th:1257180975167836171>:" if i == 4 else f"<:5th:1257180994952495114>:" if i == 5 else ""

        if i <= 5:
            message_part = f"{medal}: {row['Username']} **({row['KPH']})** {row['Nationality']} {row['Factions']} " + (f"[{row['Status']}]" if row['Status'] else "")
        else:
            message_part = f"{i}: {medal} {row['Username']} **({row['KPH']})** {row['Nationality']} {row['Factions']} " + (f"[{row['Status']}]" if row['Status'] else "")
        if len(message) + len(message_part) > 2000:
            messages.append(message)
            message = message_part
        else:
            message += "\n" + message_part

    if message:
        messages.append(message)

    changes_message = "```Changes:\n"
    for log_row in log_data:
        if log_row["status"] == "New Submission":
            changes_message += f"- Added {log_row['username']} to the leaderboard\n"
        elif log_row["status"] == "Updated Submission": 
            changes_message += f"- Updated {log_row['username']}'s KPH\n"
            if log_row["old faction"]!= log_row["new faction"]:
                old_faction_emoji = log_row["old faction"].split(':')[0][1:]
                new_faction_emoji = log_row["new faction"].split(':')[0][1:]
                changes_message += f"- {log_row['username']}, {old_faction_emoji} > {new_faction_emoji}\n"
            if log_row["old nation"]!= log_row["new nation"]:
                changes_message += f"- {log_row['username']}, {log_row['old nation']} > {log_row['new nation']}\n"
    changes_message += "```\n"

    factions_message = "\nFactions:\n"
    factions_message += "<:41st:1225417233316970576>  - 41st Strosstrupen\n"
    factions_message += "<:AH:1215458243875184652> - Austria Hungary\n"
    factions_message += "<:Farvala:1215458052451336254>  - Farvala\n"
    factions_message += "<:PLF:1215458142272356352> - Partisan Liberation Front\n"
    factions_message += "<:Russia:1215458177873608766> - Rusikiya Emperiya\n"
    factions_message += "<:WhiteLegion:1231526180583379035>  - White Legion\n"
    factions_message += "<:HFO:1215485366186942484>  - Holy Fishian Order\n"
    factions_message += "<:Toya:1215484975302967377> - Great Toya\n"
    factions_message += "<:Kozak:1215485395546939422> - Kavkazkaya Hetmanate (Kozak)\n"
    factions_message += "<:Ukraine:1236463033618923630> - Druhyy Hetʹmanat\n"
    factions_message += "<:CIA:1215487085465698385> - Confederacion Ibero-Americana\n"
    factions_message += "<:Illyria:1215497824360202240> - Eagle of Illyria\n"
    factions_message += "<:Bremen:1215485007049785408> - Bremen Uprising \n"
    factions_message += "<:Larimar:1215521967319293952> - Larimar Legion\n"
    factions_message += "<:DK:1215577329472905216> - 83rd Deathkorps\n"
    factions_message += "<:Gowa:1229576193091829850> - Sultanate of Gowa\n"
    factions_message += "<:Valient:1238798185531572244> - Valiant\n"
    factions_message += "<:Terasvia:1241204662430859355> - Terasvia\n"
    factions_message += "<:Otwoman:1244268962179715174> - Ottoman\n"
    factions_message += "<:Rumania:1252079179344777217> - Regatul României\n"
    factions_message += "<:ImperioAleman:1252080175026278440> - Imperio Aleman\n"
    factions_message += "\nLegends\n"
    factions_message += "[ <:ups:1215496391506264115> ] - Rating up\n"
    factions_message += "[ 🆕 ] - New Submission\n"

    for message in messages:
        await interaction.followup.send(message)
    await interaction.followup.send(changes_message + factions_message)

    modified_rows = []
    for log_row in log_data:
        if log_row["status"] == "New Submission" or log_row["status"] == "Updated Submission":
            modified_rows.append(log_row["username"])
    modified_statuses = [row["Status"] for row in data if row["Username"] in modified_rows]
    worksheet.update('F2:F' + str(len(modified_statuses) + 1), [[status] for status in modified_statuses])

    log_records = log_sheet.get_all_records()
    if log_records:
        if log_records[0]['username']:
            log_sheet.update('A2:I', [['' for _ in range(9)] for _ in range(len(log_records) - 1)])


def main() -> None:
    client.run(token=TOKEN)

if __name__ == '__main__':
    main()