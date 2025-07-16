from __future__ import annotations
import re
import asyncio
import requests
import discord
from discord.ext import commands
from yt_dlp import YoutubeDL
from youtubesearchpython import VideosSearch
from typing import Optional

EMBED_COLOR = 0x000000

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(
            command_prefix='.',
            intents=intents,
            activity=discord.Activity(type=discord.ActivityType.listening, name="your requests"),
            status=discord.Status.idle,
            help_command=None
        )
        self.voice_clients = {}

    async def setup_hook(self):
        await self.add_cog(MusicCog(self))

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_client = None
        self.current_track = None
        self.is_looping = False
        self.queue = []
# إعدادات اليوتيوب
ytdl_format_options = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'socket_timeout': 10,
    'extract_flat': True
}

# دالة للتحقق من روابط اليوتيوب
def is_youtube_link(message_content):
    patterns = [
        r'https?://(?:www\.)?youtu\.be/([^/?]+)',
        r'https?://(?:www\.)?youtube\.com/watch\?v=([^&]+)'
    ]
    return any(re.match(pattern, message_content) for pattern in patterns)

# دالة التحقق من صحة الرابط
def is_link_valid(url):
    try:
        response = requests.head(url, allow_redirects=True, timeout=5)
        return response.status_code == 200
    except:
        return False

# دالة تحويل الثواني لصيغة وقت
def get_duration(time):
    if time is None:
        return "بث مباشر :purple_circle:"
    hours = time // 3600
    minutes = (time % 3600) // 60
    seconds = time % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours > 0 else f"{minutes:02d}:{seconds:02d}"

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_client: Optional[discord.VoiceClient] = None
        self.is_loop = False
        self.should_skip = False
        self.current_track: dict = {}

    # دالة جلب معلومات الأغنية
    def get_audio_info(self, url: str, ctx: commands.Context) -> Optional[dict]:
        try:
            with YoutubeDL(ytdl_format_options) as ytdl:
                info = ytdl.extract_info(url, download=False)
                if 'entries' in info:
                    info = info['entries'][0]
                
                return {
                    'user': ctx.author,
                    'title': info.get('title', 'غير معروف'),
                    'url': info['url'],
                    'duration': info.get('duration'),
                    'thumbnail': info.get('thumbnail'),
                    'original_url': url
                }
        except Exception as e:
            print(f"Error getting audio info: {e}")
            return None

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"البوت اشتغل باسم {self.bot.user.name}")

    # التأكد من الاتصال بروم صوتي
    async def ensure_voice(self, ctx: commands.Context):
        if not ctx.author.voice:
            await ctx.send("ادخل للروم ولا نجي ندخلهولك")
            return False
        
        if not ctx.voice_client:
            self.voice_client = await ctx.author.voice.channel.connect()
        elif ctx.voice_client.channel != ctx.author.voice.channel:
            await ctx.voice_client.move_to(ctx.author.voice.channel)
        
        return True

    # أمر التشغيل
  @commands.command(name='play', aliases=['p', 'شغل'])
    async def play_command(self, ctx: commands.Context, *, query: Optional[str]):
        if not query:
            await ctx.send("اكتب الغنية يا شباب يا لبنين")
            return
            
        if not await self.ensure_voice(ctx):
            return

        async with ctx.typing():
            if not is_youtube_link(query):
                try:
                    search = VideosSearch(query, limit=1)
                    result = search.result()['result']
                    if not result:
                        await ctx.send("مكاش الغنية تزيد تعيني نعيييك فواحد لبلاصة")
                        return
                    url = result[0]['link']
                except Exception as e:
                    await ctx.send(f"اكتب مليح يا لهايشة {e}")
                    return
            else:
                if not is_link_valid(query):
                    await ctx.send("ميمشيش يالبنين سقسي شيكورك mirou1s#4594")
                    return
                url = query

            track_info = self.get_audio_info(url, ctx)
            if not track_info or not track_info.get('url'):
                await ctx.send("مركز استخبارات زكمها ملقاتش انفو على الغنية")
                return

            self.current_track = track_info

            try:
                source = discord.FFmpegOpusAudio(
                    track_info['url'],
                    before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
                )
                
                def after_playing(error):
                    if error:
                        print(f'Player error: {error}')
                    asyncio.run_coroutine_threadsafe(self.on_track_end(ctx), self.bot.loop)
                
                if ctx.voice_client.is_playing():
                    ctx.voice_client.stop()
                
                ctx.voice_client.play(source, after=after_playing)
                
                embed = discord.Embed(
                    title="راح تبدا الغنية اغلقها و لا نغلقهالك",
                    description=f"[{track_info['title']}]({track_info['original_url']})",
                    color=EMBED_COLOR
                )
                embed.add_field(name="وقت تمنييك", value=get_duration(track_info['duration']))
                embed.set_thumbnail(url=track_info['thumbnail'])
                embed.set_footer(text=f"لعطاي لحب يسمع {ctx.author.display_name}", 
                              icon_url=ctx.author.display_avatar.url)
                await ctx.send(embed=embed)
            except Exception as e:
                await ctx.send(f"كاين عفسا جيب الوسمو و لا سقسي شيكور {e}")

    async def on_track_end(self, ctx: commands.Context):
        if self.is_loop and not self.should_skip:
            await self.play_command(ctx, query=self.current_track.get('original_url', ''))
        else:
            self.current_track = {}
            self.should_skip = False

    # أمر التخطي
    @commands.command(name='skip', aliases=['s', 'تخطي'])
    async def skip_command(self, ctx: commands.Context):
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            await ctx.send("مكاش وش نسكيبي تزيد تعييني نعييك")
            return
            
        self.should_skip = True
        self.is_loop = False
        ctx.voice_client.stop()
        await ctx.send("لمرة لخرى نسكيبي مارانيش خدام عليك")

    # أمر الإيقاف
    @commands.command(name='stop', aliases=['leave', 'disconnect', 'وقف'])
    async def stop_command(self, ctx: commands.Context):
        if not ctx.voice_client:
            await ctx.send("يا لحمار مارانيش نغني")
            return
            
        await ctx.voice_client.disconnect()
        self.current_track = {}
        self.is_loop = False
        self.should_skip = False
        await ctx.send("اتهلا في ترمتك")

    # أمر التكرار
    @commands.command(name='repeat', aliases=['loop', 'r', 'كرر'])
    async def repeat_command(self, ctx: commands.Context):
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            await ctx.send("لمعاودة فطعام يا طري")
            return
            
        self.is_loop = not self.is_loop
        status = "rigel" if self.is_loop else "قود درك نديرهولك"
        await ctx.send(f"{status} عاودتها في خاطر الشيكور")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, 
                                 before: discord.VoiceState, 
                                 after: discord.VoiceState):
        if member.id == self.bot.user.id and after.channel is None:
            self.voice_client = None
            self.current_track = {}
            self.is_loop = False
            self.should_skip = False


async def main():
    bot = MusicBot()
    await bot.start("YOUR_BOT_TOKEN")  # استبدل بالتوكن الحقيقي

if __name__ == "__main__":
     print("""
        ┏━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃   بوت الموسيقى يشتغل  ┃
    ┃   نسخة قلبازي الذهبية ┃
    ┗━━━━━━━━━━━━━━━━━━━━━━━━┛
    """)
    asyncio.run(main())

