from src.config_loader import config
from src.logger import logger


class VideoBGMSelector:
    def __init__(self):
        self.bgm_dir = config.root_dir / "src" / "background_music"

    def get_bgm_for_category(self, category):
        """
        Returns category-based BGM path if found.

        Expected filenames:
          src/background_music/<Category>.mp3
        """
        if not category:
            return None

        if not self.bgm_dir.exists():
            logger.warning(f"BGM directory not found: {self.bgm_dir}")
            return None

        # Exact match
        exact = self.bgm_dir / f"{category}.mp3"
        if exact.exists():
            return str(exact)

        # Case-insensitive stem match
        cat_lower = str(category).strip().lower()
        for f in self.bgm_dir.glob("*.mp3"):
            if f.stem.strip().lower() == cat_lower:
                return str(f)

        return None


bgm_selector = VideoBGMSelector()