from __future__ import annotations
import os
import re
import asyncio
import discord
import requests
from discord.ext import commands
from yt_dlp import YoutubeDL
from youtubesearchpython import VideosSearch
from typing import Optional

# إعدادات الثوابت
EMBED_COLOR = 0x2b2d31  # لون الإيمبد
FFMPEG_OPTIONS = {      # إعدادات FFmpeg
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 192k',
    'executable': 'ffmpeg'  # تأكد من تثبيت FFmpeg
}

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(
            command_prefix='.',
            intents=intents,
            activity=discord.Activity(type=discord.ActivityType.listening, name="أغانيكم"),
            status=discord.Status.online,
            help_command=None
        )
        self.voice_clients = {}

    async def setup_hook(self):
        await self.add_cog(MusicCog(self))

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.loops = {}
        self.current_tracks = {}

    # دالة مساعدة للتحقق من رابط يوتيوب
    def is_youtube_url(self, url: str) -> bool:
        patterns = [
            r'(https?://)?(www\.)?youtube\.com/watch\?v=([^&]+)',
            r'(https?://)?(www\.)?youtu\.be/([^/?]+)'
        ]
        return any(re.match(pattern, url) for pattern in patterns)

    # دالة جلب معلومات الأغنية
    def get_song_info(self, query: str) -> Optional[dict]:
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'extract_flat': True,
            'noplaylist': True
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=False)
                if 'entries' in info:
                    info = info['entries'][0]
                
                return {
                    'title': info.get('title', 'غير معروف'),
                    'url': info['url'],
                    'original_url': query if self.is_youtube_url(query) else info.get('webpage_url', ''),
                    'duration': info.get('duration'),
                    'thumbnail': info.get('thumbnail')
                }
        except Exception as e:
            print(f"Error fetching song info: {e}")
            return None

    # تأكد من اتصال البوت بالروم الصوتي
    async def ensure_voice(self, ctx):
        if not ctx.author.voice:
            await ctx.send("🚫 لازم تدخل روم صوتي أولاً يا حلو!")
            return False

        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()
        elif ctx.voice_client.channel != ctx.author.voice.channel:
            await ctx.voice_client.move_to(ctx.author.voice.channel)
        
        return True

    # أمر التشغيل الأساسي
    @commands.command(name='play', aliases=['p', 'شغل'])
    async def play(self, ctx, *, query: str):
        """شغل أغنية من يوتيوب"""
        if not await self.ensure_voice(ctx):
            return

        async with ctx.typing():
            # إذا لم يكن الرابط من يوتيوب، نبحث عنه
            if not self.is_youtube_url(query):
                search = VideosSearch(query, limit=1)
                result = search.result()
                if not result['result']:
                    return await ctx.send("❌ مافي نتيجة للبحث!")
                query = result['result'][0]['link']

            song = self.get_song_info(query)
            if not song:
                return await ctx.send("❌ ما قدرت أحصل على الأغنية!")

            voice = ctx.voice_client
            if voice.is_playing():
                voice.stop()

            voice.play(discord.FFmpegPCMAudio(song['url'], **FFMPEG_OPTIONS),
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    self.on_song_end(ctx),
                    self.bot.loop
                ))

            embed = discord.Embed(
                title="🎵 بدأ التشغيل",
                description=f"[{song['title']}]({song['original_url']})",
                color=EMBED_COLOR
            )
            await ctx.send(embed=embed)
            self.current_tracks[ctx.guild.id] = song

    async def on_song_end(self, ctx):
        if self.loops.get(ctx.guild.id, False):
            await self.play(ctx, query=self.current_tracks[ctx.guild.id]['original_url'])

    # باقي الأوامر
    @commands.command(name='skip', aliases=['s', 'تخطي'])
    async def skip(self, ctx):
        """تخطي الأغنية الحالية"""
        voice = ctx.voice_client
        if not voice or not voice.is_playing():
            return await ctx.send("❌ مافي أغنية شغالة عشان تتخطاها!")
        
        voice.stop()
        await ctx.send("⏭️ تم تخطي الأغنية")

    @commands.command(name='stop', aliases=['disconnect', 'وقف'])
    async def stop(self, ctx):
        """إيقاف البوت والخروج"""
        voice = ctx.voice_client
        if not voice:
            return await ctx.send("❌ البوت مش متصل بأي روم!")
        
        await voice.disconnect()
        await ctx.send("🛑 تم إيقاف البوت")

    @commands.command(name='loop', aliases=['repeat', 'كرر'])
    async def loop(self, ctx):
        """تكرار الأغنية الحالية"""
        self.loops[ctx.guild.id] = not self.loops.get(ctx.guild.id, False)
        status = "✅ التكرار شغال" if self.loops[ctx.guild.id] else "❌ التكرار موقف"
        await ctx.send(status)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.id == self.bot.user.id and after.channel is None:
            self.current_tracks.pop(member.guild.id, None)
            self.loops.pop(member.guild.id, None)

# تشغيل البوت
async def main():
    bot = MusicBot()
    await bot.start(os.getenv('DISCORD_TOKEN'))

if __name__ == "__main__":
    print("""
    ┏━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃   بوت الموسيقى يشتغل  ┃
    ┃   بإذن الله تعالى     ┃
    ┗━━━━━━━━━━━━━━━━━━━━━━━━┛
    """)
    asyncio.run(main())
