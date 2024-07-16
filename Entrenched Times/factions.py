import discord
import json

faction_data = {}

with open('factions.json', 'r') as f:
    data = json.load(f)
    for faction_name, faction_info in data['factions'].items():
        faction_data[faction_name] = faction_info

async def cruncher(interaction: discord.Interaction, faction_name: str):
    faction_name = faction_name.strip()
    embed = discord.Embed(
        title=f"{faction_name} Details",
        description="Here are the details:",
        color=discord.Color.blurple()
    )
    embed.set_thumbnail(url=faction_data[faction_name]['thumbnail_url']) 

    faction_info = faction_data[faction_name]

    embed.add_field(name="Faction Name", value=faction_name, inline=True)
    embed.add_field(name="Region Based", value=f"\u200b{faction_info['region_based']}", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    embed.add_field(name="Descriptions", value=faction_info['descriptions'], inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=False)

    tier_rating_color = {
        "S": discord.Color.blue(),
        "A+": discord.Color.dark_blue(),
        "A": discord.Color.purple(),
        "A-": discord.Color.dark_purple(),
        "B+": discord.Color.gold(),
        "B": discord.Color.orange(),
        "B-": discord.Color.dark_orange(),
        "C+": discord.Color.brand_red(),
        "C": discord.Color.red(),
        "C-": discord.Color.dark_red(),
        "F": discord.Color.fuchsia(),
        "Discontinued": discord.Color.magenta()
    }

    embed.add_field(name="Tier rating", value=faction_info['tier_rating'], inline=True, color=tier_rating_color.get(faction_info['tier_rating'], discord.Color.default()))
    embed.add_field(name="Server Invite", value=faction_info['server_invite'], inline=True)

    embed.set_footer(text="Powered by the Entrenched Times team")

    await interaction.response.send_message(embed=embed)