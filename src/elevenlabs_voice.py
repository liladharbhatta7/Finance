import os
import json
import base64
import requests

from src.config_loader import config
from src.logger import logger


class VoiceGenerator:
    def __init__(self):
        self.api_key = config.elevenlabs_api_key
        self.voice_id = config.settings.get("ELEVENLABS_VOICE_ID", "766NdLzxBMJanRvWXtkt")
        self.model_id = config.settings.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v3")

    # ============================================================
    # PUBLIC METHOD (kept same so existing pipeline does not break)
    # ============================================================
    def generate_audio(self, text, output_path):
        """
        Generates audio and also saves a word-level timeline JSON
        with the same base filename in the same folder.

        Example:
            output_path = /tmp/story_001.mp3
            json_path   = /tmp/story_001.json

        Returns:
            True if audio generation succeeds
            False if audio generation fails
        """

        logger.info(f"Generating voice for text length: {len(text)}")

        # 1) Try timestamp-enabled endpoint first
        success = self._generate_audio_with_timestamps(text, output_path)
        if success:
            return True

        # 2) Fallback to old working audio-only endpoint
        logger.warning("Falling back to normal ElevenLabs TTS endpoint without timestamps.")
        return self._generate_audio_only(text, output_path)

    # ============================================================
    # SECTION 1: AUDIO + TIMESTAMPS GENERATION
    # ============================================================
    def _generate_audio_with_timestamps(self, text, output_path):
        """
        Uses ElevenLabs /with-timestamps endpoint.
        Saves:
          - audio file
          - word-level timeline JSON
        """

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/with-timestamps"

        headers = {
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }

        data = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.5
            }
        }

        try:
            response = requests.post(url, json=data, headers=headers, timeout=120)

            if response.status_code != 200:
                logger.error(f"ElevenLabs with-timestamps Error: {response.text}")
                return False

            result = response.json()

            # --------------------------
            # Save audio from base64
            # --------------------------
            audio_base64 = result.get("audio_base64")
            if not audio_base64:
                logger.error("No audio_base64 found in ElevenLabs with-timestamps response.")
                return False

            audio_bytes = base64.b64decode(audio_base64)
            with open(output_path, "wb") as f:
                f.write(audio_bytes)

            logger.info(f"Audio saved to {output_path}")

            # --------------------------
            # Save word timeline JSON
            # --------------------------
            alignment = result.get("alignment")
            if not alignment:
                logger.warning("No alignment found in ElevenLabs response. Audio saved, JSON not created.")
                return True

            words = self._convert_character_alignment_to_words(alignment)
            json_output_path = self._get_json_output_path(output_path)

            with open(json_output_path, "w", encoding="utf-8") as f:
                json.dump(words, f, indent=4, ensure_ascii=False)

            logger.info(f"Word timeline saved to {json_output_path}")
            return True

        except Exception as e:
            logger.error(f"Voice generation with timestamps exception: {e}")
            return False

    # ============================================================
    # SECTION 2: FALLBACK AUDIO-ONLY GENERATION
    # (kept close to your original logic for safety)
    # ============================================================
    def _generate_audio_only(self, text, output_path):
        """
        Old-style audio generation only.
        This is used as a fallback so your voice pipeline
        still works even if timestamp endpoint fails.
        """

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"

        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }

        data = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.5
            }
        }

        try:
            response = requests.post(url, json=data, headers=headers, stream=True, timeout=120)

            if response.status_code == 200:
                with open(output_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)

                logger.info(f"Audio saved to {output_path}")
                logger.warning("Audio generated without word timeline JSON because fallback endpoint was used.")
                return True

            logger.error(f"ElevenLabs Error: {response.text}")
            return False

        except Exception as e:
            logger.error(f"Voice generation exception: {e}")
            return False

    # ============================================================
    # SECTION 3: ALIGNMENT -> WORD TIMELINE CONVERSION
    # ============================================================
    def _convert_character_alignment_to_words(self, alignment):
        """
        Converts ElevenLabs character-level alignment to word-level timeline.

        Output format:
        [
            {
                "word": "नजिकको",
                "start": 0.123,
                "end": 0.567,
                "duration": 0.444
            },
            ...
        ]
        """

        characters = alignment.get("characters", [])
        starts = alignment.get("character_start_times_seconds", [])
        ends = alignment.get("character_end_times_seconds", [])

        if not characters or not starts or not ends:
            logger.warning("Alignment data is empty or incomplete.")
            return []

        words = []
        current_word = ""
        word_start_time = None

        for i, char in enumerate(characters):
            # Treat any whitespace like a separator
            if not str(char).isspace():
                if current_word == "":
                    word_start_time = starts[i]
                current_word += char
            else:
                if current_word != "":
                    words.append({
                        "word": current_word,
                        "start": round(word_start_time, 3),
                        "end": round(ends[i - 1], 3),
                        "duration": round(ends[i - 1] - word_start_time, 3)
                    })
                    current_word = ""
                    word_start_time = None

        # Handle last word if text does not end with space
        if current_word != "":
            words.append({
                "word": current_word,
                "start": round(word_start_time, 3),
                "end": round(ends[-1], 3),
                "duration": round(ends[-1] - word_start_time, 3)
            })

        return words

    # ============================================================
    # SECTION 4: FILE PATH HELPERS
    # ============================================================
    def _get_json_output_path(self, audio_output_path):
        """
        Converts:
            /path/file.mp3 -> /path/file.json
        """
        base_path, _ = os.path.splitext(audio_output_path)
        return f"{base_path}.json"


voice_generator = VoiceGenerator()