from bs4 import BeautifulSoup
import re
import asyncio
from typing import List, Dict
import aiohttp

class TwitterParser:
    def __init__(self):
        self.base_url = "https://ssstwitter.com"
        self.headers = {
            'authority': 'ssstwitter.com',
            'accept': '*/*',
            'accept-encoding': 'gzip, deflate, br, zstd',
            'accept-language': 'zh-CN,zh;q=0.9',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'hx-current-url': 'https://ssstwitter.com/',
            'hx-request': 'true',
            'hx-target': 'target',
            'origin': 'https://ssstwitter.com',
            'referer': 'https://ssstwitter.com/',
            'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        }

    def extract_video_url(self, text: str) -> str:
        """从文本中提取Twitter视频URL"""
        pattern = r'https?://(?:www\.)?(twitter\.com|x\.com)/\S+'
        match = re.search(pattern, text)
        if not match:
            raise ValueError("No Twitter video URL found in text")
        return match.group(0)

    async def get_video_info_async(self, url: str) -> Dict:
        """异步获取单个视频信息"""
        try:
            async with aiohttp.ClientSession() as session:
                # 1. 获取cookie
                async with session.get(self.base_url, headers=self.headers) as response:
                    await response.text()

                # 2. 发送POST请求
                form_data = {
                    'id': url,
                    'hx-target': 'target',
                    'hx-current-url': 'https://ssstwitter.com/'
                }

                async with session.post(
                    self.base_url,
                    headers=self.headers,
                    data=form_data
                ) as response:
                    if response.status != 200:
                        return {"status": "error", "message": "Request failed"}
                    
                    html = await response.text()

            # 3. 解析响应内容
            soup = BeautifulSoup(html, 'html.parser')
            
            # 4. 查找CDN链接
            cdn_links = soup.find_all('a', href=re.compile(r'https://ssscdn\.io'))
            
            if not cdn_links:
                return {"status": "error", "message": "No video links found"}

            # 5. 整理不同质量的视频链接
            video_qualities = {}
            for link in cdn_links:
                href = link.get('href')
                quality_text = link.get_text().strip()
                
                if 'HD' in quality_text:
                    video_qualities['HD'] = href
                elif '640x360' in quality_text:
                    video_qualities['medium'] = href
                elif '480x270' in quality_text:
                    video_qualities['low'] = href

            return {
                "status": "success",
                "message": "Video info retrieved successfully",
                "data": {
                    "url": url,
                    "videos": video_qualities
                }
            }

        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    async def batch_parse(self, urls: List[str]) -> List[Dict]:
        """批量解析视频链接"""
        tasks = [self.get_video_info_async(url) for url in urls]
        return await asyncio.gather(*tasks)
