# music/lavalink_client.py
import discord
from discord.ext import commands
import lavalink

class LavalinkVoiceClient(discord.VoiceProtocol):
    """
    This is the Lavalink voice client, subclassing discord.VoiceProtocol.
    This is used to send voice state updates to Lavalink.
    """
    def __init__(self, client: commands.Bot, channel: discord.VoiceChannel):
        super().__init__(client, channel)
        self.client = client
        self.channel = channel
        # This is the lavalink player abstraction.
        self.player = self.client.lavalink.player_manager.get(channel.guild.id)

    async def on_voice_server_update(self, data):
        lavalink_data = {
            't': 'VOICE_SERVER_UPDATE',
            'd': data
        }
        await self.client.lavalink.voice_update_handler(lavalink_data)

    async def on_voice_state_update(self, data):
        lavalink_data = {
            't': 'VOICE_STATE_UPDATE',
            'd': data
        }
        await self.client.lavalink.voice_update_handler(lavalink_data)

    async def connect(self, *, timeout: float, reconnect: bool, self_deaf: bool = False, self_mute: bool = False) -> None:
        """
        Connects to the voice channel.
        """
        # Store the voice channel id under a distinct key to avoid overwriting the text channel id
        try:
            self.player.store('voice_channel_id', self.channel.id)
        except Exception:
            pass
        await self.channel.guild.change_voice_state(channel=self.channel, self_mute=self_mute, self_deaf=self_deaf)

    async def disconnect(self, *, force: bool = False) -> None:
        """
        Disconnects from the voice channel.
        """
        player = self.client.lavalink.player_manager.get(self.channel.guild.id)

        if player:
            player.queue.clear()
            await player.stop()
            await self.client.lavalink.player_manager.destroy(self.channel.guild.id)

        await self.channel.guild.change_voice_state(channel=None)
        self.cleanup()
