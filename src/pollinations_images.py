# src/pollinations_images.py
import requests
from PIL import Image
from io import BytesIO
import os
import time
from src.logger import logger


class ImageGenerator:
    BASE_STYLE = (
       "bright studio lighting, high contrast, ultra sharp focus, "
    "clean minimal composition, modern finance theme, "
    "product photography style, crisp details, 8k clarity, "
    "blue and green color palette with subtle gold accents, "
    "no people, no faces, no hands, no body parts, "
    "no text, no watermark, no logo"
    )

    def __init__(self):
        # Keep old variable name style: api_key
        # (Only env var names are Worker-specific)
        self.worker_url = os.getenv(
            "WORKER_API_URL",
            "https://techkoseli.liladharbhatta9.workers.dev"
        )
        self.api_key = os.getenv("WORKER_API_KEY")

        if not self.api_key:
            logger.warning(
                "[WorkerAI] WORKER_API_KEY not set. Requests may fail or be rejected."
            )

    def generate_image(
        self,
        prompt: str,
        output_path: str,
        width: int = 1080,
        height: int = 1920,
        retries: int = 3,
        delay: float = 2.0
    ) -> bool:
        """
        Generate image via Cloudflare Worker AI and save it.
        Mirrors the Pollinations approach:
        - enhanced prompt
        - retries + delay
        - content-type validation
        - saves PNG for FFmpeg safety
        """

        enhanced_prompt = f"{prompt}, {self.BASE_STYLE}"
        payload = {"prompt": enhanced_prompt, "width": width, "height": height}

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json",
        }

        # Only add auth header if key exists (same technique as old code)
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        logger.info(f"[WorkerAI] Generating image: {prompt[:60]}")

        for attempt in range(1, retries + 1):
            try:
                response = requests.post(
                    self.worker_url,
                    json=payload,
                    headers=headers,
                    timeout=60
                )

                if response.status_code != 200:
                    # Include small body for debugging (safe + helpful)
                    body_preview = (response.text or "")[:300]
                    raise RuntimeError(f"HTTP {response.status_code}: {body_preview}")

                # Validate we actually got an image (same logic as before)
                content_type = response.headers.get("Content-Type", "")
                if not content_type.startswith("image/"):
                    # If worker returned JSON/text, this will catch it immediately
                    body_preview = (response.text or "")[:300]
                    raise RuntimeError(f"Invalid content-type: {content_type} | body: {body_preview}")

                img = Image.open(BytesIO(response.content)).convert("RGB")

                # PNG is safer for FFmpeg zoom/pan + subtitles
                img.save(output_path, format="PNG", optimize=True)

                logger.info(f"[WorkerAI] Image saved → {output_path}")
                return True

            except Exception as e:
                logger.warning(f"[WorkerAI] Attempt {attempt}/{retries} failed: {e}")
                if attempt < retries:
                    time.sleep(delay)

        logger.error("[WorkerAI] Image generation failed after retries")
        return False


# IMPORTANT: module-level instance so this import works:
# from src.pollinations_images import image_generator
image_generator = ImageGenerator()


if __name__ == "__main__":
    # Manual quick test
    image_generator.generate_image(
        prompt="Beautiful Himalaya mountains at sunrise",
        output_path="himalaya.png"
    )
