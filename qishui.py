import aiohttp
import re
import json
from bs4 import BeautifulSoup
from errors import InvalidURLError, VideoNotFoundError
from urllib.parse import urljoin
import asyncio
from fake_useragent import UserAgent
from typing import Dict, Any

class QishuiParser:
    """汽水音乐解析器"""
    
    def __init__(self):
        self.ua = UserAgent()
        self.session = None
        self.base_url = "https://music.douyin.com"

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    def get_headers(self) -> Dict[str, str]:
        """获取随机UA的headers"""
        return {
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'User-Agent': self.ua.random
        }

    def extract_qishui_url(self, text: str) -> str:
        """从文本中提取汽水音乐URL"""
        pattern = r'https?://qishui\.douyin\.com/\S+'
        match = re.search(pattern, text)
        if not match:
            raise ValueError("No Qishui music URL found in text")
        return match.group(0)

    def _extract_title(self, html: str) -> str:
        """提取标题"""
        soup = BeautifulSoup(html, 'html.parser')
        title_tag = soup.find('h1', class_='title')
        return title_tag.text.strip() if title_tag else "未知歌曲"

    def _extract_artist(self, soup: BeautifulSoup) -> str:
        """从页面提取艺术家信息"""
        artist_tag = soup.find('span', class_='artist-name-max')
        if artist_tag:
            return artist_tag.text.strip()
        return "未知艺术家"

    def _extract_cover(self, soup: BeautifulSoup) -> str:
        """从页面提取封面图片"""
        img_tag = soup.find('img', alt='a-image')
        if img_tag and 'src' in img_tag.attrs:
            return img_tag['src']
        return ""

    def _extract_lyrics(self, soup: BeautifulSoup) -> list:
        """从页面提取歌词"""
        lyrics = []
        lyric_divs = soup.find_all('div', class_='ssr-lyric')
        for div in lyric_divs:
            text = div.text.strip()
            if text and not text.startswith('滚动歌词&翻译贡献者'):
                lyrics.append(text)
        return lyrics

    def _extract_duration(self, soup: BeautifulSoup) -> int:
        """从页面提取歌曲时长"""
        try:
            duration_text = soup.find('div', style=lambda x: x and 'color:rgba(255, 255, 255, 0.5)' in x).text
            if duration_text:
                minutes, seconds = map(int, duration_text.split(':'))
                return minutes * 60 + seconds
        except (AttributeError, ValueError):
            pass
        return 0

    async def get_track_id(self, url: str) -> str:
        """获取音乐ID"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.get_headers(), allow_redirects=False) as response:
                    if response.status in (301, 302):
                        location = response.headers.get('Location', '')
                        track_id_match = re.search(r'track_id=(\d+)', location)
                        if track_id_match:
                            return track_id_match.group(1)
                    
                    zlink_id = url.split('/')[-1]
                    zlink_url = f"https://music.douyin.com/qishui/share/track?zlink_id={zlink_id}"
                    async with session.get(zlink_url, headers=self.get_headers()) as zlink_response:
                        html = await zlink_response.text()
                        track_id_match = re.search(r'track_id=(\d+)', html)
                        if track_id_match:
                            return track_id_match.group(1)
                            
            raise VideoNotFoundError("无法获取音乐ID")
        except Exception as e:
            raise VideoNotFoundError(f"获取音乐ID失败: {str(e)}")

    async def parse(self, url: str) -> Dict[str, Any]:
        """解析汽水音乐链接"""
        if not self.session:
            raise RuntimeError("Session not initialized. Use 'async with' context manager.")
            
        try:
            track_id = await self.get_track_id(url)
            music_url = urljoin(self.base_url, f"/qishui/share/track?track_id={track_id}")

            async with self.session.get(music_url, headers=self.get_headers(), allow_redirects=True) as response:
                if response.status != 200:
                    raise ValueError(f"Failed to fetch URL: {response.status}")
                    
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')

                audio_url = ""
                for script in soup.find_all('script'):
                    if script.string and 'window._ROUTER_DATA' in script.string:
                        try:
                            json_str = script.string.split('window._ROUTER_DATA = ')[1].split(';</script>')[0]
                            data = json.loads(json_str)
                            track_data = data.get('loaderData', {}).get('track_page', {}).get('audioWithLyricsOption', {})
                            if track_data:
                                audio_url = track_data.get('url', '')
                                break
                        except (json.JSONDecodeError, KeyError):
                            continue

                if not audio_url:
                    raise VideoNotFoundError("无法获取音频链接")

                title, artist, cover, lyrics, duration = await asyncio.gather(
                    asyncio.to_thread(self._extract_title, html),
                    asyncio.to_thread(self._extract_artist, soup),
                    asyncio.to_thread(self._extract_cover, soup),
                    asyncio.to_thread(self._extract_lyrics, soup),
                    asyncio.to_thread(self._extract_duration, soup)
                )

                return {
                    "status": "success",
                    "data": {
                        "title": title,
                        "artist": artist,
                        "cover": cover,
                        "audio_url": audio_url,
                        "duration": duration,
                        "platform": "qishui",
                        "lyrics": lyrics
                    }
                }

        except Exception as e:
            raise VideoNotFoundError(f"解析失败: {str(e)}")

