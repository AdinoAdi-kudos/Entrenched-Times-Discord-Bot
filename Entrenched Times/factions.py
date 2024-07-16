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
    embed.add_field(name="Tier rating", value=faction_info['tier_rating'], inline=True)
    embed.add_field(name="Server Invite", value=faction_info['server_invite'], inline=True)

    embed.set_footer(text="Powered by the Entrenched Times team")

    await interaction.response.send_message(embed=embed)