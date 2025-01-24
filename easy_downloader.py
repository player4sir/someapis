import aiohttp
import time
import json
import base64
import hashlib
from urllib.parse import urlparse
import traceback
import logging

logger = logging.getLogger(__name__)

class EasyDownloaderAPI:
    def __init__(self):
        """Initialize API client"""
        self.base_url = "https://api.easydownloader.app"
        self.extract_path = "/api-extract/"
        self.headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "origin": "https://easydownloader.app",
            "referer": "https://easydownloader.app/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def _generate_key(self, url):
        """Generate required key for request"""
        try:
            timestamp = str(int(time.time() * 1000))
            domain = urlparse(url).netloc
            base_str = f"{timestamp}+{domain}"
            encoded = base64.b64encode(base_str.encode()).decode()
            key = hashlib.md5(encoded.encode()).hexdigest()
            return f"{key}+hesm+ihsesnfec+ue"
        except Exception as e:
            logger.error(f"Key generation error: {str(e)}")
            return None

    def _process_response(self, json_data):
        """Process API response data"""
        if json_data.get("err") == 1:
            return {
                "status": "error",
                "message": json_data.get('msg', 'Unknown error'),
                "raw_response": json_data
            }

        if json_data.get("err") == 0:
            result = {
                "status": "success",
                "data": {
                    "videos": []
                }
            }

            if "final_urls" in json_data:
                for video in json_data["final_urls"]:
                    video_info = {
                        "title": video.get("title", ""),
                        "thumbnail": video.get("thumb", ""),
                        "page_url": video.get("url", ""),
                        "downloads": []
                    }
                    
                    if "links" in video:
                        for link in video["links"]:
                            quality_label = f"{link.get('file_quality', '')} {link.get('file_quality_units', '')}".strip()
                            download_info = {
                                "url": link.get("link_url", ""),
                                "type": link.get("file_type", ""),
                                "quality": link.get("file_quality", ""),
                                "quality_label": quality_label,
                                "filename": link.get("file_name", ""),
                                "filesize": link.get("file_size")
                            }
                            video_info["downloads"].append(download_info)
                    
                    result["data"]["videos"].append(video_info)

            return result

        return {
            "status": "error",
            "message": "Unknown response format",
            "raw_response": json_data
        }

    async def get_download_links(self, video_url):
        """Parse video URL asynchronously"""
        try:
            key = self._generate_key(video_url)
            if not key:
                return {"status": "error", "message": "Failed to generate key"}

            payload = {
                "video_url": video_url,
                "pagination": False,
                "key": key
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}{self.extract_path}",
                    headers=self.headers,
                    json=payload,
                    timeout=30
                ) as response:
                    if response.status != 200:
                        return {
                            "status": "error",
                            "message": f"Request failed with status {response.status}"
                        }

                    try:
                        json_data = await response.json()
                        return self._process_response(json_data)
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON decode error: {str(e)}")
                        return {
                            "status": "error",
                            "message": f"Failed to parse response: {str(e)}"
                        }

        except aiohttp.ClientError as e:
            return {"status": "error", "message": f"Request failed: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"} 