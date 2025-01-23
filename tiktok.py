import asyncio
import re
import aiohttp
from bs4 import BeautifulSoup
import json
import time
import random
import platform

class TiktokDownloader:
    def __init__(self):
        self.base_url = "https://tiktokio.com"
        self.download_domain = "dl.tiktokio.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.ssl_context = False
        self.prefix = None
        self.token_config = None

    async def _get_site_config(self):
        try:
            connector = aiohttp.TCPConnector(ssl=self.ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(self.base_url, headers=self.headers) as response:
                    if response.status != 200:
                        raise Exception(f"Failed to get site config: HTTP {response.status}")
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    prefix_input = soup.select_one('input[name="prefix"]')
                    if prefix_input:
                        self.prefix = prefix_input.get('value')
                    
                    scripts = soup.find_all('script')
                    for script in scripts:
                        if script.string and 'getNewUrl' in script.string:
                            config_match = re.search(r'config\s*=\s*({[^}]+})', script.string)
                            if config_match:
                                try:
                                    self.token_config = json.loads(config_match.group(1))
                                except:
                                    pass
                    
                    if not self.prefix:
                        raise Exception("Failed to extract prefix from site")
                        
        except Exception as e:
            print(f"Error getting site config: {e}")
            raise

    async def get_download_links(self, text):
        if not self.prefix:
            await self._get_site_config()
            
        video_id = await self._extract_video_id(text)
        if not video_id:
            raise ValueError("Could not extract video ID from input")

        connector = aiohttp.TCPConnector(ssl=self.ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            url = f"{self.base_url}/api/v1/tk-htmx"
            timestamp = int(time.time() * 1000)
            random_str = ''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ', k=10))
            
            params = {
                't': timestamp,
                'r': random_str
            }
            
            data = {
                'vid': f"https://www.douyin.com/video/{video_id}",
                'prefix': self.prefix
            }
            
            headers = {
                **self.headers,
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Requested-With': 'XMLHttpRequest',
                'HX-Request': 'true',
                'HX-Current-URL': self.base_url + '/',
                'HX-Target': 'tiktok-parse-result',
                'Origin': self.base_url,
                'Referer': self.base_url + '/'
            }
            
            if self.token_config:
                for key, value in self.token_config.items():
                    data[key] = value
            
            try:
                async with session.post(
                    url, 
                    params=params,
                    data=data,
                    headers=headers,
                    timeout=30
                ) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP error {response.status}")
                    
                    html = await response.text()
                    return await self._parse_response(html)
                    
            except Exception as e:
                print(f"Error crawling video: {e}")
                raise

    async def _parse_response(self, html):
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            title = soup.select_one('#tk-search-h2')
            title = title.text.strip() if title else None
            
            cover = soup.select_one('img[src*="webp"]') 
            cover_url = cover.get('src') if cover else None
            
            download_links = {
                'no_watermark': None,
                'no_watermark_hd': None, 
                'watermark': None,
                'audio': None
            }
            
            for link in soup.select('.tk-down-link a'):
                href = link.get('href')
                text = link.text.lower()
                
                if not href or not href.startswith(f'https://{self.download_domain}/download'):
                    continue
                    
                if 'without watermark (hd)' in text:
                    download_links['no_watermark_hd'] = href
                elif 'without watermark' in text:
                    download_links['no_watermark'] = href
                elif 'watermark' in text:
                    download_links['watermark'] = href
                elif 'mp3' in text:
                    download_links['audio'] = href
            
            result = {
                "status": "success",
                "data": {
                    "title": title,
                    "cover": cover_url,
                    "downloads": {
                        "video": {
                            "no_watermark": download_links['no_watermark'],
                            "no_watermark_hd": download_links['no_watermark_hd'],
                            "watermark": download_links['watermark']
                        },
                        "audio": download_links['audio']
                    }
                }
            }
            
            if not any(download_links.values()):
                result['status'] = 'error'
                result['message'] = 'No download links found'
            
            return result
            
        except Exception as e:
            print(f"Error parsing response: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    async def _extract_video_id(self, text):
        try:
            url_pattern = r'https?://[^\s<>"]+?(?:\s|$)'
            url_match = re.search(url_pattern, text)
            if not url_match:
                raise ValueError("No URL found in text")
            
            url = url_match.group(0).strip()

            if 'v.douyin.com' in url or 'vm.tiktok.com' in url:
                connector = aiohttp.TCPConnector(ssl=self.ssl_context)
                async with aiohttp.ClientSession(connector=connector) as session:
                    try:
                        timeout = aiohttp.ClientTimeout(total=30)
                        async with session.get(
                            url, 
                            headers=self.headers, 
                            allow_redirects=True,
                            timeout=timeout
                        ) as response:
                            if response.status != 200:
                                raise Exception(f"Failed to follow redirect: HTTP {response.status}")
                            final_url = str(response.url)
                    except Exception as e:
                        print(f"Error following redirect: {e}")
                        final_url = url
            else:
                final_url = url

            video_id_patterns = [
                r'/video/(\d+)',
                r'item_ids=(\d+)',
                r'/(\d{15,21})'
            ]
            
            for pattern in video_id_patterns:
                if match := re.search(pattern, final_url):
                    return match.group(1)
                    
            return None
                
        except Exception as e:
            print(f"Error extracting video ID: {e}")
            return None 