import hashlib
from urllib.parse import urlparse, urlunparse
import requests
import re
import time
from typing import List, Dict, Any

class SpotifyDownloader:
    BASE_URL = "https://spotifymate.com"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
        'Accept': '*/*',
        'Origin': BASE_URL,
        'Referer': f"{BASE_URL}/en"
    }
    PATTERNS = {
        'token': r'<input\s+name=["\']([^"\']+)["\']\s+type=["\']hidden["\']\s+value=["\']([^"\']+)["\']',
        'download': r'<a[^>]*href=["\']((?:https?:)?//[^"\']*?/dl\?token=[^"\']*)["\'][^>]*>(?:<span><span>([^<]+)</span></span>)</a>'
    }

    def __init__(self):
        self.session = requests.Session()

    def _get_token(self) -> tuple:
        """获取页面 token"""
        response = self.session.get(f"{self.BASE_URL}/en", headers=self.HEADERS, timeout=10)
        if match := re.search(self.PATTERNS['token'], response.text):
            return match.group(1), match.group(2)
        raise ValueError("无法获取 token")

    def _normalize_url(self, url: str) -> str:
        """规范化 Spotify URL"""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        parsed = urlparse(url)
        if 'spotify.com' not in parsed.netloc:
            raise ValueError("请使用 Spotify 域名的 URL")
        return urlunparse(parsed._replace(query="", fragment=""))

    def get_download_links(self, spotify_url: str, max_retries: int = 3) -> Dict[str, Any]:
        """获取下载链接"""
        for attempt in range(max_retries):
            try:
                normalized_url = self._normalize_url(spotify_url)
                token_name, token_value = self._get_token()
                
                response = self.session.post(
                    f"{self.BASE_URL}/action",
                    data={
                        'url': normalized_url,
                        '_lvrcs': hashlib.md5(normalized_url.encode()).hexdigest(),
                        token_name: token_value
                    },
                    headers=self.HEADERS,
                    timeout=10
                )
                
                for match in re.finditer(self.PATTERNS['download'], response.text):
                    href, text = match.groups()
                    if 'Cover' not in text:  # 只处理 MP3 链接
                        if not href.startswith('http'):
                            href = 'https:' + href if href.startswith('//') else self.BASE_URL + href
                        return {
                            "status": "success",
                            "data": {
                                "url": href
                            }
                        }
                    
            except Exception as e:
                if attempt == max_retries - 1:
                    return {
                        "status": "error",
                        "message": f"下载失败: {str(e)}"
                    }
                time.sleep(1)
        
        return {
            "status": "error",
            "message": "未找到下载链接"
        } 