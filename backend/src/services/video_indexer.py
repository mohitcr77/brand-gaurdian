import os
import time
import logging
import requests
import yt_dlp
from azure.identity import DefaultAzureCredential

logger = logging.getLogger("video-indexer")

# Azure ARM tokens are valid for ~60 minutes — cache to avoid redundant calls
_TOKEN_CACHE: dict = {"token": None, "expires_at": 0}

# Maximum time (seconds) to wait for Azure Video Indexer to process a video
PROCESSING_TIMEOUT_SECONDS = 600  # 10 minutes


class VideoIndexerService:
    def __init__(self):
        self.account_id = os.getenv("AZURE_VI_ACCOUNT_ID")
        self.location = os.getenv("AZURE_VI_LOCATION")
        self.subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
        self.resource_group = os.getenv("AZURE_RESOURCE_GROUP")
        self.vi_name = os.getenv("AZURE_VI_NAME", "project-brand-guardian-001")
        self.credential = DefaultAzureCredential()

    def get_access_token(self) -> str:
        """
        Returns a cached ARM access token, refreshing only when expired.
        Tokens are valid ~60 min — caching avoids one network call per poll cycle.
        """
        now = time.time()
        if _TOKEN_CACHE["token"] and now < _TOKEN_CACHE["expires_at"]:
            return _TOKEN_CACHE["token"]

        try:
            token_object = self.credential.get_token("https://management.azure.com/.default")
            _TOKEN_CACHE["token"] = token_object.token
            # Refresh 5 minutes before actual expiry to avoid edge cases
            _TOKEN_CACHE["expires_at"] = token_object.expires_on - 300
            logger.info("ARM access token refreshed.")
            return _TOKEN_CACHE["token"]
        except Exception as e:
            logger.error(f"Failed to get Azure Token: {e}")
            raise

    def get_account_token(self, arm_access_token: str) -> str:
        """Exchanges an ARM token for a Video Indexer account-scoped token."""
        url = (
            f"https://management.azure.com/subscriptions/{self.subscription_id}"
            f"/resourceGroups/{self.resource_group}"
            f"/providers/Microsoft.VideoIndexer/accounts/{self.vi_name}"
            f"/generateAccessToken?api-version=2024-01-01"
        )
        headers = {"Authorization": f"Bearer {arm_access_token}"}
        payload = {"permissionType": "Contributor", "scope": "Account"}
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to get VI Account Token: {response.text}")
        return response.json().get("accessToken")

    def download_youtube_video(self, url: str, output_path: str = "temp_video.mp4") -> str:
        """Downloads a YouTube video to a local file using yt-dlp."""
        logger.info(f"Downloading YouTube video: {url}")

        ydl_opts = {
            "format": "best",
            "outtmpl": output_path,
            "quiet": False,
            "no_warnings": False,
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36"
                )
            },
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            logger.info("Download complete.")
            return output_path
        except Exception as e:
            raise RuntimeError(f"YouTube download failed: {e}") from e

    def upload_video(self, video_path: str, video_name: str) -> str:
        """Uploads a local video file to Azure Video Indexer."""
        arm_token = self.get_access_token()
        vi_token = self.get_account_token(arm_token)

        api_url = (
            f"https://api.videoindexer.ai/{self.location}"
            f"/Accounts/{self.account_id}/Videos"
        )
        params = {
            "accessToken": vi_token,
            "name": video_name,
            "privacy": "Private",
            "indexingPreset": "Default",
        }

        logger.info(f"Uploading {video_path} to Azure Video Indexer...")
        with open(video_path, "rb") as video_file:
            response = requests.post(api_url, params=params, files={"file": video_file})

        if response.status_code != 200:
            raise RuntimeError(f"Azure upload failed: {response.text}")

        return response.json().get("id")

    def wait_for_processing(self, video_id: str) -> dict:
        """
        Polls Azure Video Indexer until processing is complete or times out.
        Raises TimeoutError if processing exceeds PROCESSING_TIMEOUT_SECONDS.
        """
        logger.info(f"Waiting for video {video_id} to process...")
        deadline = time.time() + PROCESSING_TIMEOUT_SECONDS

        while time.time() < deadline:
            arm_token = self.get_access_token()  # Uses cache — no extra network call
            vi_token = self.get_account_token(arm_token)

            url = (
                f"https://api.videoindexer.ai/{self.location}"
                f"/Accounts/{self.account_id}/Videos/{video_id}/Index"
            )
            response = requests.get(url, params={"accessToken": vi_token})
            data = response.json()

            state = data.get("state")
            if state == "Processed":
                logger.info("Video processing complete.")
                return data
            elif state == "Failed":
                raise RuntimeError("Azure Video Indexer: processing failed.")
            elif state == "Quarantined":
                raise RuntimeError("Azure Video Indexer: video quarantined (copyright/content policy).")

            logger.info(f"Status: {state} — retrying in 30s...")
            time.sleep(30)

        raise TimeoutError(
            f"Video {video_id} did not finish processing within "
            f"{PROCESSING_TIMEOUT_SECONDS // 60} minutes."
        )

    def extract_data(self, vi_json: dict) -> dict:
        """Parses the Video Indexer JSON response into the graph state format."""
        transcript_lines = []
        ocr_lines = []

        for video in vi_json.get("videos", []):
            insights = video.get("insights", {})
            for entry in insights.get("transcript", []):
                if entry.get("text"):
                    transcript_lines.append(entry["text"])
            for entry in insights.get("ocr", []):
                if entry.get("text"):
                    ocr_lines.append(entry["text"])

        duration = (
            vi_json.get("summarizedInsights", {})
            .get("duration", {})
            .get("seconds")
        )

        return {
            "transcript": " ".join(transcript_lines),
            "ocr_text": ocr_lines,
            "video_metadata": {
                "duration": duration,
                "platform": "youtube",
            },
        }
