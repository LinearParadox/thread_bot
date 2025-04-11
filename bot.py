import discord
from dotenv import load_dotenv
from discord.ext import commands
import os
import json


load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

# File to store configuration
CONFIG_FILE = "thread_config.json"

# Load configuration
def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            # Initialize thread_summary_channels if it doesn't exist
            if "thread_summary_channels" not in config:
                config["thread_summary_channels"] = {}
            return config
    except (FileNotFoundError, json.JSONDecodeError):
        return {"tracked_channels": {}, "thread_summary_channels": {}}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

config = load_config()

client = commands.Bot(command_prefix='$', intents=intents)

# Function to update thread summary
async def update_thread_summary(guild_id):
    """
    Updates the thread summary message with all active threads in tracked channels
    """
    if guild_id not in config["thread_summary_channels"]:
        return  # No summary channel configured for this guild
    
    summary_channel_id = config["thread_summary_channels"][guild_id]
    guild = client.get_guild(int(guild_id))
    if not guild:
        return
    
    summary_channel = guild.get_channel(int(summary_channel_id))
    if not summary_channel:
        return
    
    # Build the summary message
    summary = []
    
    # Only proceed if there are tracked channels in this guild
    if guild_id in config["tracked_channels"]:
        for channel_id in config["tracked_channels"][guild_id]:
            channel = guild.get_channel(int(channel_id))
            if not channel:
                continue
                
            # Add channel header in large text
            summary.append(f"# {channel.name}")
            
            # Get all threads in this channel
            threads = [thread for thread in channel.threads]
            
            # Add threads or placeholder
            if threads:
                for thread in threads:
                    summary.append(f"• {thread.name}")
            else:
                summary.append("*No active threads*")
            
            summary.append("")  # Add empty line between channels
    
    summary_text = "\n".join(summary) if summary else "No tracked channels with active threads."
    
    try:
        # Clear any existing messages
        async for message in summary_channel.history(limit=10):
            if message.author == client.user:
                await message.delete()
        
        # Send new summary message
        await summary_channel.send(summary_text)
    except discord.Forbidden:
        print(f"Missing permissions for thread summary in guild {guild_id}")
    except Exception as e:
        print(f"Error updating thread summary: {e}")

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    
@client.event
async def on_thread_create(thread):
    """
    This event triggers whenever a new thread is created in any server the bot can see
    """
    # Only respond if the thread is from a tracked channel
    if thread.parent:
        guild_id = str(thread.guild.id)
        channel_id = thread.parent.id
        
        # Check if this channel is being tracked
        if (guild_id in config["tracked_channels"] and 
            str(channel_id) in config["tracked_channels"][guild_id]):
            
            print(f"New thread created: {thread.name} in channel #{thread.parent.name}")
            await thread.send(f"Welcome to the thread '{thread.name}'!")
            
            # Update thread summary
            await update_thread_summary(guild_id)

@client.event
async def on_thread_delete(thread):
    """
    This event triggers whenever a thread is deleted
    """
    if thread.parent:
        guild_id = str(thread.guild.id)
        channel_id = thread.parent.id
        
        # Check if this channel is being tracked
        if (guild_id in config["tracked_channels"] and 
            str(channel_id) in config["tracked_channels"][guild_id]):
            
            print(f"Thread deleted: {thread.name} in channel #{thread.parent.name}")
            
            # Update thread summary
            await update_thread_summary(guild_id)

@client.command(name="track_channel")
@commands.has_permissions(administrator=True)
async def track_channel(ctx):
    """
    Set up thread tracking for the current channel
    """
    channel = ctx.channel
    guild_id = str(ctx.guild.id)
    
    # Initialize guild in config if not exists
    if guild_id not in config["tracked_channels"]:
        config["tracked_channels"][guild_id] = []
    
    # Check if already tracking
    if str(channel.id) in config["tracked_channels"][guild_id]:
        await ctx.send(f"Already tracking threads in channel '{channel.name}'.")
        return
    
    # Add channel to tracked list
    config["tracked_channels"][guild_id].append(str(channel.id))
    save_config(config)
    
    await ctx.send(f"Now tracking threads in channel '{channel.name}'.")
    
    # Update thread summary
    await update_thread_summary(guild_id)

@client.command(name="untrack_channel")
@commands.has_permissions(administrator=True)
async def untrack_channel(ctx):
    """
    Stop thread tracking for the current channel
    """
    channel = ctx.channel
    guild_id = str(ctx.guild.id)
    
    # Check if we're tracking this channel
    if (guild_id not in config["tracked_channels"] or
        str(channel.id) not in config["tracked_channels"][guild_id]):
        await ctx.send(f"Not tracking threads in channel '{channel.name}'.")
        return
    
    # Remove channel from tracked list
    config["tracked_channels"][guild_id].remove(str(channel.id))
    save_config(config)
    
    await ctx.send(f"Stopped tracking threads in channel '{channel.name}'.")
    
    # Update thread summary
    await update_thread_summary(guild_id)

@client.command(name="list_tracked")
async def list_tracked(ctx):
    """
    List all channels where thread tracking is enabled
    """
    guild_id = str(ctx.guild.id)
    
    if guild_id not in config["tracked_channels"] or not config["tracked_channels"][guild_id]:
        await ctx.send("No channels are being tracked in this server.")
        return
    
    tracked_channels = []
    for channel_id in config["tracked_channels"][guild_id]:
        channel = ctx.guild.get_channel(int(channel_id))
        if channel:
            tracked_channels.append(f"• #{channel.name}")
    
    if tracked_channels:
        await ctx.send("**Tracked Channels:**\n" + "\n".join(tracked_channels))
    else:
        await ctx.send("No valid channels are being tracked in this server.")

@client.command(name="set_summary_channel")
@commands.has_permissions(administrator=True)
async def set_summary_channel(ctx):
    """
    Set the current channel as the thread summary channel
    """
    channel = ctx.channel
    guild_id = str(ctx.guild.id)
    
    # Store the summary channel ID
    config["thread_summary_channels"][guild_id] = str(channel.id)
    save_config(config)
    
    await ctx.send(f"This channel has been set as the thread summary channel.")
    
    # Update the summary immediately
    await update_thread_summary(guild_id)

client.run(TOKEN)