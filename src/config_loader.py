import os
import yaml
import json
from dotenv import load_dotenv
from pathlib import Path
from src.logger import logger

# Load .env if exists (local dev)
load_dotenv()

class Config:
    def __init__(self):
        self.root_dir = Path(__file__).resolve().parent.parent
        self.config_dir = self.root_dir / "config"
        self.assets_dir = self.root_dir / "assets"
        self.state_dir = self.root_dir / "state"
        self.output_dir = self.root_dir / "outputs"
        
        # Ensure directories
        self.state_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
        
        # Load settings
        self.settings = self._load_settings()
        
        # Secrets (Env vars take precedence over settings.yaml)
        self.gemini_api_key = os.getenv("GEMINI_API_KEY") or self.settings.get("GEMINI_API_KEY")
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY") or self.settings.get("ELEVENLABS_API_KEY")
        self.youtube_client_id = os.getenv("YOUTUBE_CLIENT_ID") or self.settings.get("YOUTUBE_CLIENT_ID")
        self.youtube_client_secret = os.getenv("YOUTUBE_CLIENT_SECRET") or self.settings.get("YOUTUBE_CLIENT_SECRET")
        self.youtube_refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN") or self.settings.get("YOUTUBE_REFRESH_TOKEN")
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or self.settings.get("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID") or self.settings.get("TELEGRAM_CHAT_ID")

        # Facebook
        self.facebook_page_id = os.getenv("FACEBOOK_PAGE_ID") or self.settings.get("FACEBOOK_PAGE_ID")
        self.facebook_page_access_token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN") or self.settings.get("FACEBOOK_PAGE_ACCESS_TOKEN")
        self.facebook_graph_api_version = os.getenv("FACEBOOK_GRAPH_API_VERSION") or self.settings.get("FACEBOOK_GRAPH_API_VERSION", "v25.0")

    def _load_settings(self):
        settings_path = self.config_dir / "settings.yaml"
        if not settings_path.exists():
            # Fallback to example if no settings file (e.g. CI environment relying only on env vars)
            logger.warning("settings.yaml not found, checking settings.yaml.example or relying on env vars.")
            settings_path = self.config_dir / "settings.yaml.example"
            
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            return {}

    def get_topics(self):
        with open(self.config_dir / "topics.json", 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_gemini_prompt(self):
        with open(self.config_dir / "gemini_prompt.txt", 'r', encoding='utf-8') as f:
            return f.read()

config = Config()