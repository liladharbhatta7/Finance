from pathlib import Path

from src.config_loader import config
from src.logger import logger


class VideoSFXSelector:
    def __init__(self):
        self.sfx_dir = config.root_dir / "src" / "sfx"

        self.keyword_map = {
            "coin": [
                "रुपैयाँ", "रु", "पैसा", "कमाइ", "बचत", "आम्दानी", "income", "money", "profit", "return"
            ],
            "pop": [
                "%", "प्रतिशत", "inflation", "महँगी", "fd", "bank", "loan", "emi", "tax", "कर"
            ],
            "impact": [
                "तर", "सावधान", "गलत", "खतरनाक", "घाटा", "loss", "myth", "mistake"
            ]
        }

    def build_events(self, timeline_data, category=None):
        """
        Returns list of SFX events:
        [
            {"time": 1.2, "path": ".../pop.wav", "volume": 0.55},
            ...
        ]
        """
        events = []
        last_sfx_time = -999.0

        # 1) scene transition whoosh
        for scene in timeline_data.get("scenes", []):
            if scene["index"] > 0:
                whoosh_path = self._get_sfx_path("Tech Whoosh")
                if whoosh_path:
                    t = max(0.0, scene["start"] - 0.06)
                    if t - last_sfx_time >= 0.8:
                        events.append({
                            "time": round(t, 3),
                            "path": whoosh_path,
                            "volume": 0.45
                        })
                        last_sfx_time = t

        # 2) keyword-driven sfx from words
        for w in timeline_data.get("words", []):
            word = str(w.get("word", "")).strip()
            if not word:
                continue

            matched_name = self._match_word_to_sfx(word)
            if not matched_name:
                continue

            sfx_path = self._get_sfx_path(matched_name)
            if not sfx_path:
                continue

            t = float(w.get("start", 0))
            if t - last_sfx_time < 0.9:
                continue

            volume = 0.50
            if matched_name == "coin":
                volume = 0.55
            elif matched_name == "impact":
                volume = 0.60

            events.append({
                "time": round(t, 3),
                "path": sfx_path,
                "volume": volume
            })
            last_sfx_time = t

        logger.info(f"SFX events selected: {len(events)}")
        return events

    def _match_word_to_sfx(self, word):
        word_l = word.lower()

        for key, keywords in self.keyword_map.items():
            for kw in keywords:
                if kw.lower() in word_l:
                    return key
        return None

    def _get_sfx_path(self, name):
        if not self.sfx_dir.exists():
            logger.warning(f"SFX directory not found: {self.sfx_dir}")
            return None

        candidates = [
            self.sfx_dir / f"{name}.wav",
            self.sfx_dir / f"{name}.mp3",
        ]

        for p in candidates:
            if p.exists():
                return str(p)

        return None


sfx_selector = VideoSFXSelector()