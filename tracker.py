import asyncio
import os
import json
import logging
import subprocess
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


class TikTokTracker:

    async def verify_account(self, username: str) -> bool:
        try:
            result = await asyncio.to_thread(
                self._run_yt_dlp,
                [
                    "--flat-playlist",
                    "--playlist-end", "1",
                    "--dump-single-json",
                    "--no-warnings",
                    f"https://www.tiktok.com/@{username}",
                ]
            )
            return result is not None
        except Exception as e:
            logger.error(f"verify_account error for @{username}: {e}")
            return False

    async def get_new_videos(self, username: str) -> List[Tuple[str, str, str]]:
        try:
            result = await asyncio.to_thread(
                self._run_yt_dlp,
                [
                    "--flat-playlist",
                    "--playlist-end", "5",
                    "--dump-single-json",
                    "--no-warnings",
                    f"https://www.tiktok.com/@{username}",
                ]
            )
            if not result:
                return []
            data = json.loads(result)
            videos = []
            for entry in data.get("entries", []):
                video_id = entry.get("id", "")
                url = entry.get("url") or entry.get("webpage_url") or f"https://www.tiktok.com/@{username}/video/{video_id}"
                description = entry.get("title", "") or entry.get("description", "")
                if video_id:
                    videos.append((url, video_id, description))
            return videos
        except Exception as e:
            logger.error(f"get_new_videos error for @{username}: {e}")
            return []

    async def download_video(self, url: str, video_id: str) -> Optional[str]:
        output_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp4")
        if os.path.exists(output_path):
            return output_path
        try:
            await asyncio.to_thread(
                self._run_yt_dlp,
                [
                    "-o", output_path,
                    "--no-warnings",
                    "--merge-output-format", "mp4",
                    url,
                ],
                capture_output=False
            )
            if os.path.exists(output_path):
                return output_path
            return None
        except Exception as e:
            logger.error(f"download_video error for {url}: {e}")
            return None

    def _run_yt_dlp(self, args: list, capture_output: bool = True) -> Optional[str]:
        cmd = ["yt-dlp"] + args
        try:
            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=True,
                timeout=60
            )
            if capture_output and result.returncode == 0:
                return result.stdout.strip()
            elif not capture_output and result.returncode == 0:
                return "ok"
            else:
                logger.warning(f"yt-dlp exited with code {result.returncode}")
                return None
        except subprocess.TimeoutExpired:
            logger.error("yt-dlp timed out")
            return None
        except FileNotFoundError:
            logger.error("yt-dlp not found. Please install it: pip install yt-dlp")
            return None
