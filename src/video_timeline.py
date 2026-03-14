import json
from pathlib import Path

from src.logger import logger


class VideoTimelineBuilder:
    def build(self, scenes, audio_path=None):
        """
        Builds timeline from scenes and optional word-level timeline JSON.

        JSON path rule:
            /path/story_narration.mp3 -> /path/story_narration.json
        """

        timeline_scenes = []
        current_time = 0.0

        for idx, scene in enumerate(scenes):
            duration = float(scene.get("duration", 5))
            start = round(current_time, 3)
            end = round(current_time + duration, 3)

            timeline_scenes.append({
                "index": idx,
                "image_path": scene.get("image_path"),
                "text": scene.get("text", ""),
                "duration": duration,
                "start": start,
                "end": end,
                "words": []
            })

            current_time += duration

        words = self._load_word_timeline(audio_path) if audio_path else []

        # assign words to scene buckets
        if words:
            for scene in timeline_scenes:
                scene_words = []
                for w in words:
                    w_start = float(w.get("start", 0))
                    if scene["start"] <= w_start < scene["end"]:
                        scene_words.append(w)
                scene["words"] = scene_words

        return {
            "scenes": timeline_scenes,
            "words": words,
            "total_duration": round(current_time, 3)
        }

    def _load_word_timeline(self, audio_path):
        try:
            json_path = Path(audio_path).with_suffix(".json")
            if not json_path.exists():
                logger.warning(f"Timeline JSON not found for audio: {json_path}")
                return []

            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, list):
                logger.warning(f"Timeline JSON is not a list: {json_path}")
                return []

            return data

        except Exception as e:
            logger.warning(f"Failed to load word timeline JSON: {e}")
            return []


timeline_builder = VideoTimelineBuilder()