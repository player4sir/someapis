import base64
import requests
import aiohttp
import asyncio
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Any

class DouYinParser:
    def __init__(self):
        self.base_url = "https://snapdouyin.app"
        self.api_endpoint = "/wp-json/mx-downloader/video-data/"
        self.session = self._init_session()
        self.token = None

    def _init_session(self):
        """初始化会话和请求头"""
        session = requests.Session()
        session.headers.update({
            'accept': '*/*',
            'accept-language': 'zh-CN,zh;q=0.9',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://snapdouyin.app',
            'referer': 'https://snapdouyin.app/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        })
        return session

    def extract_video_url(self, text: str) -> str:
        """从文本中提取抖音视频URL"""
        # 匹配抖音链接的正则表达式模式
        patterns = [
            r'https?://(?:v\.douyin\.com|www\.douyin\.com|douyin\.com)/[^\s]+',
            r'https?://(?:www\.iesdouyin\.com)/[^\s]+',
            # 短链接格式
            r'https?://[^\s]*douyin[^\s]*',
            # 提取分享文本中的链接
            r'(?<=复制此链接，打开抖音搜索，直接观看视频！)\s*(https?://[^\s]+)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                # 返回找到的第一个链接
                return matches[0].strip()
        
        raise ValueError("No valid Douyin URL found in text")

    async def _async_get_token(self, session: aiohttp.ClientSession) -> str:
        """异步获取页面token"""
        try:
            async with session.get(self.base_url) as response:
                text = await response.text()
                
                # 使用BeautifulSoup解析HTML
                soup = BeautifulSoup(text, 'html.parser')
                token_input = soup.find('input', {'id': 'token'})
                if token_input and 'value' in token_input.attrs:
                    return token_input['value']
                
                # 从脚本中查找token
                scripts = soup.find_all('script')
                for script in scripts:
                    if script.string and 'token' in script.string:
                        match = re.search(r'token["\s:]+(["\'])([^"\']+)\1', script.string)
                        if match:
                            return match.group(2)
                
                raise ValueError("Token not found in page")
                
        except Exception as e:
            raise Exception(f"Failed to get token: {str(e)}")

    async def _async_get_real_url(self, session: aiohttp.ClientSession, media_id: str, headers: dict) -> str:
        """异步获取真实下载URL"""
        temp_url = f"{self.base_url}/wp-content/plugins/aio-video-downloader/download.php?source=douyin&media={media_id}&bandwidth_saving=1"
        
        async with session.get(temp_url, headers=headers) as resp:
            try:
                data = await resp.json()
                if 'url' in data:
                    return data['url']
            except:
                if 'Location' in resp.headers:
                    return resp.headers['Location']
                elif str(resp.url) != temp_url:
                    return str(resp.url)
            
            return None

    async def get_video_info_async(self, video_url: str) -> Dict[str, Any]:
        """异步获取视频信息"""
        try:
            # 创建异步会话
            async with aiohttp.ClientSession() as session:
                # 设置headers
                session.headers.update(self.session.headers)
                
                # 获取token
                if not self.token:
                    self.token = await self._async_get_token(session)

                # 标准化URL
                video_url = self.normalize_url(video_url)
                
                # 构建请求数据
                data = {
                    'url': video_url,
                    'token': self.token,
                    'hash': self.calculate_hash(video_url)
                }

                # 获取视频信息
                async with session.post(urljoin(self.base_url, self.api_endpoint), data=data) as response:
                    if response.status == 403:
                        self.token = await self._async_get_token(session)
                        data['token'] = self.token
                        async with session.post(urljoin(self.base_url, self.api_endpoint), data=data) as response:
                            result = await response.json()
                    else:
                        result = await response.json()

                if 'medias' not in result:
                    raise ValueError("No media found in response")

                # 构建返回数据
                video_info = {
                    'status': 'success',
                    'message': 'Video information retrieved successfully',
                    'data': {
                        'title': result.get('title', ''),
                        'author': result.get('author', ''),
                        'thumbnail': result.get('thumbnail', ''),
                        'duration': result.get('duration', ''),
                        'create_time': result.get('create_time', ''),
                        'formats': []
                    }
                }

                # 异步获取所有格式的真实URL
                tasks = []
                for i, media in enumerate(result['medias']):
                    if media.get('url'):
                        media_id = base64.b64encode(str(i).encode()).decode()
                        task = self._async_get_real_url(session, media_id, dict(session.headers))
                        tasks.append((media, task))

                # 等待所有URL获取完成
                for media, task in tasks:
                    real_url = await task
                    if real_url:
                        format_info = {
                            'quality': media.get('quality', ''),
                            'format': media.get('extension', ''),
                            'size': media.get('formattedSize', ''),
                            'size_bytes': media.get('size', 0),
                            'download_url': real_url,
                            'has_video': media.get('videoAvailable', False),
                            'has_audio': media.get('audioAvailable', False),
                            'format_note': self._get_format_note(media)
                        }
                        video_info['data']['formats'].append(format_info)

                return video_info

        except Exception as e:
            return {
                'status': 'error',
                'message': str(e),
                'data': None
            }

    async def batch_parse(self, urls: List[str]) -> List[Dict[str, Any]]:
        """批量解析视频信息"""
        tasks = [self.get_video_info_async(url) for url in urls]
        return await asyncio.gather(*tasks)

    def calculate_hash(self, url: str, salt: str = 'aio-dl') -> str:
        """计算请求hash"""
        url_b64 = base64.b64encode(url.encode()).decode()
        salt_b64 = base64.b64encode(salt.encode()).decode()
        return f"{url_b64}{len(url) + 1000}{salt_b64}"

    def normalize_url(self, url: str) -> str:
        """标准化视频URL"""
        pattern = r'(http|ftp|https):\/\/([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:\/~+#-]*[\w@?^=%&\/~+#-])'
        match = re.search(pattern, url)
        if match:
            return match.group(0)
        raise ValueError("Invalid URL format")

    def _get_format_note(self, media: dict) -> str:
        """生成格式说明"""
        notes = []
        if media.get('videoAvailable'):
            notes.append('Video')
        if media.get('audioAvailable'):
            notes.append('Audio')
        quality = media.get('quality', '')
        if '⭐' in quality:
            notes.append('Best Quality')
        return ' + '.join(notes)
