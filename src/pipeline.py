import os
import time
import subprocess
from pathlib import Path
from src.logger import logger
from src.config_loader import config
from src.gemini_story import gemini_generator
from src.pollinations_images import image_generator
from src.elevenlabs_voice import voice_generator
from src.video_ffmpeg import video_editor
from src.thumbnail import thumbnail_generator
from src.youtube_upload import youtube_uploader
from src.facebook_upload import facebook_uploader
from src.report import report_manager
from src.utils_time import validate_schedule_time, npt_to_utc_iso

class VideoPipeline:
    def __init__(self):
        self.temp_dir = config.root_dir / "temp"
        self.output_dir = config.output_dir
        self.temp_dir.mkdir(exist_ok=True)

    def _get_audio_duration_sec(self, audio_path: str) -> float:
        """
        Returns duration of audio file in seconds using ffprobe.
        """
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return float(result.stdout.strip())

    def process_story(self, topic, schedule_time_npt):
        story_id = f"{time.strftime('%Y-%m-%d')}_{topic['id']}"
        topic_id = topic['id']
        logger.info(f"Starting pipeline for {story_id}")

        # 1. Generate Script
        try:
            story = gemini_generator.generate_story(topic)
        except Exception as e:
            report_manager.add_entry(story_id, topic_id, "N/A", "N/A", None, "FAILED", f"Script Gen missing: {e}")
            return

        title = story.get("title", "Nepali Short")
        scenes = story.get("scenes", [])
        narration = story.get("narration_text", "")
        
        # 2. Generate Audio
        audio_path = self.temp_dir / f"{story_id}_narration.mp3"
        if not voice_generator.generate_audio(narration, audio_path):
             report_manager.add_entry(story_id, topic_id, title, "N/A", None, "FAILED", "Audio Gen failed")
             return

        # 3. Generate Scene Images
        processed_scenes = []
        for i, scene in enumerate(scenes):
            prompt = scene.get("visual_prompt", "")
            duration = scene.get("duration_sec", 5)
            text = scene.get("on_screen_text", "")
            
            img_path = self.temp_dir / f"{story_id}_scene_{i}.jpg"
            if image_generator.generate_image(prompt, img_path):
                processed_scenes.append({
                    "image_path": str(img_path),
                    "text": text,
                    "duration": duration
                })
            else:
                logger.warning(f"Skipping scene {i} due to image generation failure")

        if not processed_scenes:
            report_manager.add_entry(story_id, topic_id, title, "N/A", None, "FAILED", "No scenes generated")
            return

        # ✅ Normalize total scene duration to match narration duration
        try:
            narration_sec = self._get_audio_duration_sec(str(audio_path))
            scenes_sec = sum(float(s["duration"]) for s in processed_scenes)
            diff = narration_sec - scenes_sec

            # Adjust only if mismatch is noticeable
            if abs(diff) > 0.3:
                last_before = float(processed_scenes[-1]["duration"])
                processed_scenes[-1]["duration"] = max(2.0, last_before + diff)
                logger.info(
                    f"Adjusted last scene duration by {diff:.2f}s to match narration. "
                    f"Last scene: {last_before:.2f}s -> {processed_scenes[-1]['duration']:.2f}s | "
                    f"Scenes total was {scenes_sec:.2f}s, narration is {narration_sec:.2f}s"
                )
        except Exception as e:
            logger.warning(f"Could not normalize scene durations to narration length: {e}")

        # 4. Assemble Video
        video_path = self.output_dir / f"{story_id}.mp4"
        if not video_editor.assemble_video(
            processed_scenes,
            str(audio_path),
            str(video_path),
            str(self.temp_dir),
            topic.get("category")  # ✅ pass category so correct BGM is selected
        ):
            report_manager.add_entry(story_id, topic_id, title, "N/A", None, "FAILED", "Video assembly failed")
            return

        # 5. Thumbnail (Optional uses first image)
        thumb_path = self.output_dir / f"{story_id}_thumb.png"
        thumbnail_generator.create_thumbnail(processed_scenes[0]['image_path'], title, str(thumb_path))

        # 6. Upload  ✅ FIX: handle both string ISO and datetime input safely
        if isinstance(schedule_time_npt, str):
            utc_publish_time = schedule_time_npt
        else:
            utc_publish_time = npt_to_utc_iso(validate_schedule_time(schedule_time_npt))
        
        description = f"{title}\n\n{story['narration_text'][:200]}...\n\n#shorts #nepali #story"
        tags = story.get("hashtags", []) + ["shorts", "nepali"]
        
        yt_video_id = youtube_uploader.upload_video(
            str(video_path),
            title,
            description,
            tags,
            utc_publish_time
        )

        fb_video_id = facebook_uploader.upload_video(
            str(video_path),
            title,
            description,
            tags,
            utc_publish_time
        )

        if yt_video_id or fb_video_id:
            combined_ids = f"YT:{yt_video_id or 'None'} | FB:{fb_video_id or 'None'}"
            report_manager.add_entry(
                story_id,
                topic_id,
                title,
                str(schedule_time_npt),
                combined_ids,
                "SUCCESS" if yt_video_id else "PARTIAL_SUCCESS",
                None if yt_video_id and fb_video_id else "One platform upload failed"
            )
        else:
            report_manager.add_entry(
                story_id,
                topic_id,
                title,
                str(schedule_time_npt),
                None,
                "FAILED",
                "YouTube and Facebook upload both failed"
            )

        # Cleanup
        self._cleanup(story_id)

    def _cleanup(self, story_id):
        # Delete temp files starting with story_id
        for p in self.temp_dir.glob(f"{story_id}*"):
            try:
                p.unlink()
            except:
                pass

pipeline = VideoPipeline()
