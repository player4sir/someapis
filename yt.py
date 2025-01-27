import requests
import base64
import time
import json
import re
import urllib3
from typing import Dict, Optional, Any

class YouTubeMP3Converter:
    """YouTube MP3 转换器"""
    
    def __init__(self, base_url: str = "ytmp3.la", backend: str = "ummn.nu", config_cache_time: int = 300):
        # 基础配置
        self.base_url = base_url
        self.backend = backend
        self.format = "mp3"
        self.config_cache_time = config_cache_time
        self.last_config_time = 0
        self.config = None
        
        # 初始化会话
        self.session = self._init_session()
        
        # 初始配置
        self._refresh_config()

    def _init_session(self) -> requests.Session:
        """初始化请求会话"""
        session = requests.Session()
        session.verify = False
        urllib3.disable_warnings()
        
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': f'https://{self.base_url}',
            'Referer': f'https://{self.base_url}/'
        })
        
        return session

    def _should_refresh_config(self) -> bool:
        """检查是否需要刷新配置"""
        return (
            not self.config or 
            time.time() - self.last_config_time > self.config_cache_time
        )

    def _refresh_config(self) -> None:
        """刷新配置"""
        self.config = self._fetch_config()
        self.last_config_time = time.time()

    def _fetch_config(self) -> Dict[str, Any]:
        """获取网站配置"""
        sources = [
            (f'https://{self.base_url}', self._extract_from_html),
            (f'https://{self.base_url}/js/ytmp3.js', self._extract_from_js)
        ]
        
        errors = []
        for url, extractor in sources:
            try:
                response = self.session.get(url, timeout=10)
                if response.status_code == 200:
                    if config := extractor(response.text):
                        if self._validate_config(config):
                            return config
            except Exception as e:
                errors.append(f"{url}: {str(e)}")
                continue
        
        raise Exception(f"无法获取配置: {'; '.join(errors)}")

    def _extract_from_html(self, content: str) -> Optional[Dict[str, Any]]:
        """从HTML中提取配置"""
        for script in re.findall(r'<script[^>]*>(.*?)</script>', content, re.DOTALL):
            if config := self._extract_config(script):
                return config
        return None

    def _extract_from_js(self, content: str) -> Optional[Dict[str, Any]]:
        """从JS文件中提取配置"""
        return self._extract_config(content)

    def _extract_config(self, content: str) -> Optional[Dict[str, Any]]:
        """提取配置"""
        if eval_match := re.search(r"eval\(atob\('([^']+)'\)\);", content):
            try:
                decoded = base64.b64decode(eval_match.group(1)).decode()
                if gc_match := re.search(r'var\s+gC\s*=\s*({[^;]+});', decoded):
                    return json.loads(gc_match.group(1).replace("'", '"'))
            except:
                pass
        return None

    def _validate_config(self, config: Dict[str, Any]) -> bool:
        """验证配置是否有效"""
        try:
            required_keys = ['0', '1', '2', 'f', 'r']
            if not all(key in config for key in required_keys):
                return False
            
            if not isinstance(config['f'], list) or len(config['f']) < 8:
                return False
                
            if not all(isinstance(config[key], str) for key in ['0', '1', '2']):
                return False
                
            return True
            
        except:
            return False

    def _generate_signature(self, initial_value: str = "") -> str:
        """生成签名"""
        try:
            numbers = base64.b64decode(self.config['0']).decode().split(self.config['f'][6])
            result = initial_value
            
            base_str = self.config['1']
            if int(self.config['f'][5]) > 0:
                base_str = ''.join(reversed(base_str))
            
            for num in numbers:
                idx = int(num) - int(self.config['f'][4])
                if 0 <= idx < len(base_str):
                    result += base_str[idx]
            
            if int(self.config['f'][2]) == 1:
                result = result.lower()
            elif int(self.config['f'][2]) == 2:
                result = result.upper()
            
            if self.config['f'][1] and len(self.config['f'][1]) > 0:
                result = self.config['f'][1]
            elif int(self.config['f'][3]) > 0:
                result = result[:int(self.config['f'][3]) + 1]
            
            return result
            
        except Exception as e:
            raise Exception(f"生成签名失败: {str(e)}")

    def _make_request(self, url: str, params: Optional[Dict[str, str]] = None, retry_count: int = 3) -> Dict[str, Any]:
        """发送请求"""
        last_error = None
        
        for attempt in range(retry_count):
            try:
                if attempt > 0:
                    self._refresh_config()
                
                headers = dict(self.session.headers)
                if 'r' in self.config:
                    rapidapi = 'rapidapi'
                    headers.update({
                        f'x-{rapidapi}-host': f"{self.config['r'][0]}{rapidapi}.com",
                        f'x-{rapidapi}-key': self.config['r'][1]
                    })
                
                response = self.session.get(url, params=params, headers=headers, timeout=10)
                response.raise_for_status()
                
                result = response.json()
                if error := result.get('error'):
                    if int(str(error)) > 0:
                        raise Exception(f"API错误: {error}")
                return result
                
            except Exception as e:
                last_error = e
                if attempt < retry_count - 1:
                    time.sleep(1)
                    continue
                
        raise Exception(f"请求失败: {str(last_error)}")

    def get_download_url(self, url: str, max_retries: int = 3) -> Dict[str, Any]:
        """获取下载链接"""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # 每次尝试都刷新配置
                self._refresh_config()
                
                video_id = self._extract_video_id(url)
                
                # 生成初始化参数
                signature = self._generate_signature(self.config['f'][7])
                k_param = base64.b64encode(
                    f"{self.config['2']}-{signature}".encode()
                ).decode()
                
                # 初始化请求
                init_data = self._make_request(
                    f"https://d.{self.backend}/api/v1/init",
                    {'k': k_param, '_': str(int(time.time() * 1000))}
                )
                
                # 转换请求
                convert_url = init_data['convertURL']
                params = {
                    'v': f"https://www.youtube.com/watch?v={video_id}",
                    'f': self.format,
                    '_': str(int(time.time() * 1000))
                }
                
                # 处理重定向和进度
                for _ in range(5):
                    result = self._make_request(convert_url, params)
                    
                    if download_url := result.get('downloadURL'):
                        return {
                            "status": "success",
                            "data": {
                                "title": result.get('title', ''),
                                "url": download_url
                            }
                        }
                    
                    if progress_url := result.get('progressURL'):
                        result = self._wait_progress(progress_url)
                        return {
                            "status": "success", 
                            "data": {
                                "title": result.get('title', ''),
                                "url": result['url']
                            }
                        }
                    
                    if result.get('redirect') == 1 and (url := result.get('redirectURL')):
                        convert_url = url
                        continue
                
                raise Exception("获取下载链接失败")
                
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
        
        raise Exception(f"转换失败: {str(last_error)}")

    def _extract_video_id(self, url: str) -> str:
        """提取视频ID"""
        patterns = {
            'youtu.be': r'youtu\.be/([^?]+)',
            'youtube.com': r'[?&]v=([^&]+)',
            'music.youtube.com': r'[?&]v=([^&]+)'
        }
        
        for domain, pattern in patterns.items():
            if domain in url and (match := re.search(pattern, url)):
                return match.group(1)
                
        raise ValueError("无效的YouTube URL")

    def _wait_progress(self, url: str, max_attempts: int = 30, delay: int = 3) -> Dict[str, str]:
        """等待转换进度"""
        for _ in range(max_attempts):
            result = self._make_request(url)
            
            if download_url := result.get('downloadURL'):
                return {
                    'url': download_url,
                    'title': result.get('title', '')
                }
            
            time.sleep(delay)
            
        raise Exception("转换超时")

def main():
    try:
        converter = YouTubeMP3Converter()
        url = input("\n请输入YouTube视频URL: ").strip()
        result = converter.get_download_url(url)
        
        if result['status'] == 'success':
            print(f"\n标题: {result['data']['title']}")
            print(f"下载链接: {result['data']['url']}")
        else:
            print(f"\n错误: {result.get('message', '未知错误')}")
            
    except Exception as e:
        print(f"\n错误: {str(e)}")

if __name__ == "__main__":
    main() 