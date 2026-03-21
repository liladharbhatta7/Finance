import os
import time
import datetime
import mimetypes
import requests

from src.config_loader import config
from src.logger import logger


class FacebookUploader:
    """
    Interface intentionally matches YouTubeUploader:
        upload_video(video_path, title, description, tags, publish_at_iso)
    """

    def __init__(self):
        self.page_id = getattr(config, "facebook_page_id", None)
        self.page_access_token = getattr(config, "facebook_page_access_token", None)
        self.graph_api_version = getattr(config, "facebook_graph_api_version", "v25.0")
        self.base_url = f"https://graph-video.facebook.com/{self.graph_api_version}"

        # Safe defaults; kept internal so current pipeline does not need changes.
        self.finish_retry_count = 2
        self.finish_retry_sleep_seconds = 5
        self.fallback_to_immediate_publish = True

    def _validate_config(self):
        if not self.page_id:
            logger.error("No Facebook Page ID found.")
            return False
        if not self.page_access_token:
            logger.error("No Facebook Page access token found.")
            return False
        return True

    def _parse_publish_time_to_unix(self, publish_at_iso):
        """
        Input example:
            2026-03-13T15:30:00.000Z
        """
        try:
            dt = datetime.datetime.strptime(publish_at_iso, "%Y-%m-%dT%H:%M:%S.000Z")
            dt = dt.replace(tzinfo=datetime.timezone.utc)
            return int(dt.timestamp())
        except Exception as e:
            logger.error(f"Invalid publish_at_iso format: {publish_at_iso} | {e}")
            return None

    def _safe_scheduled_publish_time(self, publish_at_iso):
        scheduled_unix = self._parse_publish_time_to_unix(publish_at_iso)
        if scheduled_unix is None:
            return None

        now_unix = int(time.time())
        min_allowed = now_unix + 15 * 60  # safe buffer

        if scheduled_unix < min_allowed:
            logger.warning("Facebook schedule time too close/past. Pushing to 15 minutes later.")
            scheduled_unix = min_allowed

        return scheduled_unix

    def _build_description(self, description, tags):
        """
        Facebook does not use YouTube-style keyword tags the same way.
        So we append them as hashtags in description.
        """
        description = (description or "").strip()
        tags = tags or []

        hashtags = []
        for tag in tags:
            if not tag:
                continue
            clean = str(tag).strip().replace(" ", "")
            if not clean:
                continue
            if not clean.startswith("#"):
                clean = f"#{clean}"
            hashtags.append(clean)

        if hashtags:
            if description:
                return f"{description}\n\n{' '.join(hashtags)}"
            return " ".join(hashtags)

        return description

    def _raise_for_response(self, response, action):
        if response.ok:
            return

        try:
            payload = response.json()
        except Exception:
            payload = response.text

        logger.error(f"Facebook API error during {action}: {response.status_code} | {payload}")
        raise Exception(f"Facebook API error during {action}: {response.status_code} | {payload}")

    def _start_upload_session(self, file_size):
        url = f"{self.base_url}/{self.page_id}/videos"
        data = {
            "access_token": self.page_access_token,
            "upload_phase": "start",
            "file_size": file_size,
        }

        response = requests.post(url, data=data, timeout=120)
        self._raise_for_response(response, "start")

        payload = response.json()
        return {
            "upload_session_id": payload["upload_session_id"],
            "video_id": payload.get("video_id"),
            "start_offset": int(payload["start_offset"]),
            "end_offset": int(payload["end_offset"]),
        }

    def _transfer_chunks(self, video_path, upload_session_id, start_offset, end_offset):
        url = f"{self.base_url}/{self.page_id}/videos"
        mime_type = mimetypes.guess_type(video_path)[0] or "video/mp4"

        with open(video_path, "rb") as f:
            while start_offset < end_offset:
                chunk_size = end_offset - start_offset
                f.seek(start_offset)
                chunk = f.read(chunk_size)

                files = {
                    "video_file_chunk": (os.path.basename(video_path), chunk, mime_type)
                }
                data = {
                    "access_token": self.page_access_token,
                    "upload_phase": "transfer",
                    "upload_session_id": upload_session_id,
                    "start_offset": str(start_offset),
                }

                response = requests.post(url, data=data, files=files, timeout=300)
                self._raise_for_response(response, "transfer")

                payload = response.json()
                start_offset = int(payload["start_offset"])
                end_offset = int(payload["end_offset"])

                logger.info(f"Facebook upload progress: next_start={start_offset}, next_end={end_offset}")

    def _finish_upload(self, upload_session_id, title, description, publish_at_iso, immediate=False):
        url = f"{self.base_url}/{self.page_id}/videos"

        data = {
            "access_token": self.page_access_token,
            "upload_phase": "finish",
            "upload_session_id": upload_session_id,
            "title": (title or "")[:255],
            "description": (description or "")[:10000],
        }

        if immediate or not publish_at_iso:
            data["published"] = "true"
            logger.info("Facebook finish mode: immediate publish")
        else:
            scheduled_publish_time = self._safe_scheduled_publish_time(publish_at_iso)
            if scheduled_publish_time is None:
                raise Exception("Could not parse publish_at_iso.")

            data["published"] = "false"
            data["scheduled_publish_time"] = str(scheduled_publish_time)
            logger.info(f"Facebook finish mode: scheduled publish at unix={scheduled_publish_time}")

        response = requests.post(url, data=data, timeout=120)
        self._raise_for_response(response, "finish")

        return response.json()

    def _finish_with_retry_or_fallback(self, upload_session_id, title, description, publish_at_iso):
        last_error = None

        # First try scheduled mode if schedule exists
        if publish_at_iso:
            attempts = self.finish_retry_count + 1
            for attempt in range(1, attempts + 1):
                try:
                    logger.info(f"Facebook scheduled finish attempt {attempt}/{attempts}")
                    return self._finish_upload(
                        upload_session_id=upload_session_id,
                        title=title,
                        description=description,
                        publish_at_iso=publish_at_iso,
                        immediate=False,
                    )
                except Exception as e:
                    last_error = e
                    if attempt < attempts:
                        sleep_for = self.finish_retry_sleep_seconds * attempt
                        logger.warning(
                            f"Facebook scheduled finish attempt {attempt} failed. "
                            f"Retrying in {sleep_for}s. Error: {e}"
                        )
                        time.sleep(sleep_for)
                    else:
                        logger.warning(
                            "Facebook scheduled upload failed after retries."
                        )

            if self.fallback_to_immediate_publish:
                logger.warning(
                    "Falling back to immediate Facebook publish because scheduled finish failed."
                )
                return self._finish_upload(
                    upload_session_id=upload_session_id,
                    title=title,
                    description=description,
                    publish_at_iso=None,
                    immediate=True,
                )

            raise last_error

        # No schedule provided -> publish immediately
        return self._finish_upload(
            upload_session_id=upload_session_id,
            title=title,
            description=description,
            publish_at_iso=None,
            immediate=True,
        )

    def upload_video(self, video_path, title, description, tags, publish_at_iso):
        if not self._validate_config():
            return None

        if not os.path.exists(video_path):
            logger.error(f"Facebook upload failed. File not found: {video_path}")
            return None

        try:
            file_size = os.path.getsize(video_path)
            final_description = self._build_description(description, tags)

            logger.info(f"Uploading to Facebook: {title}")
            logger.info(f"Facebook scheduled time (UTC ISO input): {publish_at_iso}")

            session = self._start_upload_session(file_size)
            self._transfer_chunks(
                video_path=video_path,
                upload_session_id=session["upload_session_id"],
                start_offset=session["start_offset"],
                end_offset=session["end_offset"],
            )

            finish_payload = self._finish_with_retry_or_fallback(
                upload_session_id=session["upload_session_id"],
                title=title,
                description=final_description,
                publish_at_iso=publish_at_iso,
            )

            video_id = (
                finish_payload.get("video_id")
                or finish_payload.get("id")
                or session.get("video_id")
            )

            logger.info(f"Facebook upload complete. Video ID: {video_id}")
            return video_id

        except Exception as e:
            logger.error(f"Facebook upload failed: {e}")
            return None


facebook_uploader = FacebookUploader()