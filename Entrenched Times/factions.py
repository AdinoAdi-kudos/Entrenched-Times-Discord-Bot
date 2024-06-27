import discord
import csv

faction_data = {}

with open('factions.txt', 'r') as f:
    reader = csv.reader(f)
    for row in reader:
        faction_name, region_based, descriptions, tier_rating, server_invite, thumbnail_url = row
        faction_data[faction_name] = {
            'region_based': region_based,
            'descriptions': descriptions,
            'tier_rating': tier_rating,
            'server_invite': server_invite,
            'thumbnail_url': thumbnail_url
        }

async def cruncher(interaction: discord.Interaction, faction_name: str):
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
    embed.add_field(name="Tier rating", value=faction_info['tier_rating'], inline=True)
    embed.add_field(name="Server Invite", value=faction_info['server_invite'], inline=True)

    embed.set_footer(text="Powered by the Entrenched Times team")

    await interaction.response.send_message(embed=embed)