import aiohttp
import base64
import time
import re
import json
import asyncio
from typing import Dict, Any

class YouTubeDownloader:
    def __init__(self):
        self.base_domain = "ummn.nu"
        self.api_domain = "rapidapi.com"
        self.format = "mp3"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://ytmp3.la",
            "Referer": "https://ytmp3.la/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
        }
        
        self.max_retries = 3
        self.retry_delay = 2
        
    def _extract_video_id(self, url: str) -> str:
        """Extract YouTube video ID from URL"""
        patterns = [
            r'youtu\.be\/([a-zA-Z0-9\-\_]{11})',
            r'youtube\.com\/shorts\/([a-zA-Z0-9\-\_]{11})',
            r'v=([a-zA-Z0-9\-\_]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    async def _get_gc_config(self) -> Dict[str, Any]:
        """Get gC configuration asynchronously"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    "https://ytmp3.la/",
                    headers=self.headers,
                    timeout=10
                ) as response:
                    if response.status != 200:
                        raise Exception(f"Failed to get website content: {response.status}")
                    
                    html_content = await response.text()
                    script_pattern = r'<script>eval\(atob\(\'(.*?)\'\)\);</script>'
                    script_match = re.search(script_pattern, html_content)
                    
                    if not script_match:
                        raise Exception("Could not find gC configuration in website")
                    
                    gc_base64 = script_match.group(1)
                    decoded = base64.b64decode(gc_base64).decode()
                    gc_json = decoded[decoded.find("{"):decoded.rfind("}") + 1]
                    gc_json = gc_json.replace("'", '"')
                    return json.loads(gc_json)
                    
            except Exception as e:
                raise Exception(f"Failed to get gC config: {str(e)}")

    async def _generate_key(self) -> str:
        """Generate dynamic key based on JavaScript implementation"""
        try:
            gc = await self._get_gc_config()
            decoded = base64.b64decode(gc["0"]).decode()
            parts = decoded.split(gc["f"][4])
            salt = gc["1"]
            
            if int(gc["f"][3]) > 0:
                salt = ''.join(reversed(salt))
            
            key = ""
            for part in parts:
                try:
                    idx = int(part) - int(gc["f"][2])
                    if 0 <= idx < len(salt):
                        key += salt[idx]
                except ValueError:
                    continue
            
            if int(gc["f"][0]) == 1:
                key = key.lower()
            elif int(gc["f"][0]) == 2:
                key = key.upper()
            
            if int(gc["f"][1]) > 0:
                key = gc["f"][5] + key[:int(gc["f"][1])]
            else:
                key = gc["f"][5] + key
            
            return f"{gc['2']}-{key}"
            
        except Exception as e:
            raise Exception(f"Failed to generate key: {str(e)}")

    async def _init_conversion(self, video_id: str) -> Dict[str, Any]:
        """Initialize the conversion process asynchronously"""
        async with aiohttp.ClientSession() as session:
            try:
                init_key = await self._generate_key()
                init_url = f"https://d.{self.base_domain}/api/v1/init"
                params = {
                    "k": base64.b64encode(init_key.encode()).decode(),
                    "_": str(int(time.time() * 1000))
                }
                
                async with session.get(
                    init_url,
                    params=params,
                    headers=self.headers,
                    timeout=10
                ) as response:
                    if response.status != 200:
                        raise Exception(f"Init failed with status code: {response.status}")
                    
                    data = await response.json()
                    error = int(data.get("error", 0))
                    if error > 0:
                        raise Exception(f"Server returned error: {error}")
                    
                    return data
                
            except Exception as e:
                raise Exception(f"Init conversion failed: {str(e)}")

    async def _start_conversion(self, convert_url: str, video_id: str) -> Dict[str, Any]:
        """Start the conversion process asynchronously"""
        async with aiohttp.ClientSession() as session:
            try:
                init_key = await self._generate_key()
                params = {
                    "v": f"https://www.youtube.com/watch?v={video_id}",
                    "f": self.format,
                    "_": str(int(time.time() * 1000)),
                    "k": base64.b64encode(init_key.encode()).decode()
                }
                
                async with session.get(
                    convert_url, 
                    params=params, 
                    headers=self.headers,
                    timeout=10
                ) as response:
                    if response.status != 200:
                        raise Exception(f"Conversion failed with status code: {response.status}")
                    
                    try:
                        text = await response.text()
                        # 处理转义字符
                        text = text.replace('\\u0026', '&')
                        data = json.loads(text)
                        
                        if data.get("redirect", 0) == 1:
                            # 处理重定向URL
                            redirect_url = data.get("redirectURL", "").replace('\\', '')
                            if redirect_url:
                                return await self._start_conversion(redirect_url, video_id)
                        
                        return data
                        
                    except json.JSONDecodeError as e:
                        raise Exception(f"Failed to parse server response: {text}")
                
            except Exception as e:
                raise Exception(f"Conversion request failed: {str(e)}")

    async def _check_progress(self, progress_url: str) -> Dict[str, Any]:
        """Check conversion progress asynchronously"""
        retry_count = 0
        
        async with aiohttp.ClientSession() as session:
            while retry_count < self.max_retries:
                try:
                    init_key = await self._generate_key()
                    params = {
                        "_": str(int(time.time() * 1000)),
                        "k": base64.b64encode(init_key.encode()).decode()
                    }
                    
                    async with session.get(
                        progress_url, 
                        headers=self.headers,
                        params=params,
                        timeout=10
                    ) as response:
                        if response.status != 200:
                            raise Exception(f"Progress check failed with status code: {response.status}")
                        
                        try:
                            text = await response.text()
                            # 处理转义字符
                            text = text.replace('\\u0026', '&')
                            data = json.loads(text)
                            
                            error = int(data.get("error", 0))
                            progress = int(data.get("progress", 0))
                            
                            if error > 0:
                                raise Exception(f"Conversion error: {error}")
                            
                            if progress >= 3:
                                return data
                            
                            await asyncio.sleep(3)
                            retry_count += 1
                            
                        except json.JSONDecodeError as e:
                            raise Exception(f"Failed to parse progress response: {text}")
                        
                except Exception as e:
                    retry_count += 1
                    if retry_count >= self.max_retries:
                        raise
                    await asyncio.sleep(2)
            
            raise Exception("Progress check timed out")

    async def get_download_url(self, video_url: str) -> Dict[str, str]:
        """Get download URL for YouTube video asynchronously"""
        try:
            video_id = self._extract_video_id(video_url)
            if not video_id:
                raise ValueError("Invalid YouTube URL")
            
            init_data = await self._init_conversion(video_id)
            convert_url = init_data.get("convertURL")
            if not convert_url:
                raise Exception("Failed to get conversion URL")
            
            conv_data = await self._start_conversion(convert_url, video_id)
            if conv_data.get("redirect", 0) == 1:
                conv_data = await self._start_conversion(conv_data["redirectURL"], video_id)
            
            progress_data = await self._check_progress(conv_data["progressURL"])
            
            return {
                "download_url": conv_data["downloadURL"],
                "title": progress_data.get("title", ""),
                "format": self.format,
                "video_id": video_id
            }
            
        except Exception as e:
            raise


