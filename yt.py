import requests
import base64
import time
import json
import re
import urllib3
from typing import Dict, Any

class YouTubeDownloader:
    def __init__(self):
        """Initialize the YouTube downloader"""
        # Initialize session and configuration
        self.session = requests.Session()
        self.session.verify = False
        urllib3.disable_warnings()
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0',
            'Origin': 'https://ytmp3.la',
            'Referer': 'https://ytmp3.la/'
        })
        
        self.format = "mp3"
        self.config = self._get_initial_config()
        
    def _get_initial_config(self) -> Dict[str, Any]:
        """Get initial configuration from the website"""
        response = self.session.get('https://ytmp3.la')
        if match := re.search(r"eval\(atob\('([^']+)'\)\);", response.text):
            decoded = base64.b64decode(match.group(1)).decode()
            if gc_match := re.search(r'var\s+gC\s*=\s*({[^;]+});', decoded):
                return json.loads(gc_match.group(1).replace("'", '"'))
        raise Exception("Failed to get initial configuration")

    def _extract_video_id(self, url: str) -> str:
        """Extract YouTube video ID from URL"""
        patterns = [
            r'youtu\.be\/([a-zA-Z0-9\-\_]{11})',
            r'youtube\.com\/shorts\/([a-zA-Z0-9\-\_]{11})',
            r'[?&]v=([a-zA-Z0-9\-\_]{11})'
        ]
        
        for pattern in patterns:
            if match := re.search(pattern, url):
                return match.group(1)
        return None

    def _generate_signature(self) -> str:
        """Generate signature for API requests"""
        numbers = base64.b64decode(self.config['0']).decode().split(self.config['f'][6])
        base_str = self.config['1'][::-1] if self.config['f'][5] > 0 else self.config['1']
        
        signature = ''.join(
            base_str[int(num) - self.config['f'][4]]
            for num in numbers
            if 0 <= (idx := int(num) - self.config['f'][4]) < len(base_str)
        )
        
        if self.config['f'][2] == 2:
            signature = signature.upper()
            
        return f"{self.config['2']}-.{signature}"

    def _wait_for_progress(self, url: str, max_attempts: int = 30) -> Dict[str, Any]:
        """Wait for conversion progress and get download URL"""
        for _ in range(max_attempts):
            result = self.session.get(url).json()
            
            if download_url := result.get('downloadURL'):
                return {
                    'download_url': download_url,
                    'title': result.get('title', ''),
                    'format': self.format
                }
            
            if error := result.get('error'):
                raise Exception(f"Conversion error: {error}")
                
            time.sleep(3)
            
        raise Exception("Conversion timeout")

    async def get_download_url(self, video_url: str) -> Dict[str, str]:
        """Get download URL for YouTube video"""
        try:
            video_id = self._extract_video_id(video_url)
            if not video_id:
                raise ValueError("Invalid YouTube URL")

            # Generate signature and initialize conversion
            k_param = base64.b64encode(self._generate_signature().encode()).decode()
            init_data = self.session.get(
                'https://d.ummn.nu/api/v1/init',
                params={'k': k_param, '_': str(int(time.time() * 1000))}
            ).json()

            if not init_data.get('convertURL'):
                raise Exception("Failed to get conversion URL")

            # Start conversion process
            params = {
                'v': f"https://www.youtube.com/watch?v={video_id}",
                'f': self.format,
                '_': str(int(time.time() * 1000))
            }

            convert_url = init_data['convertURL']
            for _ in range(5):  # Maximum 5 redirects
                result = self.session.get(convert_url, params=params).json()
                
                if download_url := result.get('downloadURL'):
                    return {
                        'download_url': download_url,
                        'title': result.get('title', ''),
                        'format': self.format,
                        'video_id': video_id
                    }
                    
                if progress_url := result.get('progressURL'):
                    result = self._wait_for_progress(progress_url)
                    result['video_id'] = video_id
                    return result
                    
                if result.get('redirect') == 1 and (redirect_url := result.get('redirectURL')):
                    convert_url = redirect_url
                    continue
                    
                raise Exception("Failed to get download URL")

        except Exception as e:
            raise Exception(f"Download failed: {str(e)}")


