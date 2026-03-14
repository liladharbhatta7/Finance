import json
import os
import re
from dataclasses import dataclass, asdict
from typing import List, Dict, Any

# ----------------------------
# CONFIG
# ----------------------------
INPUT_FILE = "timeline.json"
OUTPUT_FILE = "typography_plan.json"

FINANCE_WORDS = {"पैसा", "लगानी", "सेयर", "डिभिडेन्ड", "जोखिम", "बजार", "IPO", "FOMO", "EPS", "NFT", "FD", "महँगी", "ब्याज", "कर"}
DANGER_WORDS = {"खतरा", "धोका", "अपराध", "अवैध", "कानुनी", "गुम्छ", "डुब्छ", "नोक्सान"}
RARE_WORDS = {"विशेष", "सुपर", "सबैभन्दा", "पहिलो", "अनौठो", "ट्रिक", "वास्तविक"}
EMOTION_WORDS = {"धनी", "गरीब", "खुशी", "दुःखी", "आश्चर्य", "आक्रोश", "डर", "लोभ"}
QUESTION_WORDS = {"किन", "के", "कसरी", "कहिले", "कति"}
CONTRAST_WORDS = {"तर", "तर पनि", "वास्तवमा", "अझै", "फेरि", "मात्र"}
STOPWORDS = {"र", "त", "छ", "का", "को", "लाई", "मा", "ने", "यो", "त्यो", "यदि", "भने"}

MAX_BLOCK_WORDS = 6
MIN_BLOCK_WORDS = 1
LONG_PAUSE_THRESHOLD = 0.38
VERY_LONG_PAUSE_THRESHOLD = 0.65
MAX_BLOCK_DURATION = 2.2
MIN_BLOCK_DURATION = 0.55


# ----------------------------
# Data models
# ----------------------------
@dataclass
class WordItem:
    text: str
    start: float
    end: float
    duration: float
    pause_before: float = 0.0
    score: int = 0

@dataclass
class CaptionBlock:
    id: int
    start: float
    end: float
    duration: float
    text: str
    words: List[Dict[str, Any]]
    role: str
    energy: str
    layout: str
    style: Dict[str, Any]
    animation: Dict[str, Any]
    highlight_words: List[str]


# ----------------------------
# Helpers
# ----------------------------
def clean_word(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).strip())

def has_number(text: str) -> bool:
    return any(ch.isdigit() for ch in text)

def ends_sentence(text: str) -> bool:
    return text.endswith(("।", ".", "!", "?"))

def is_question_text(text: str) -> bool:
    if "?" in text:
        return True
    tokens = text.split()
    return any(t in QUESTION_WORDS for t in tokens)

def safe_round(x: float) -> float:
    return round(float(x), 2)


# ----------------------------
# Load + normalize
# ----------------------------
def load_timeline(path: str) -> List[WordItem]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Input file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if not raw:
        return []

    sample = raw[0]
    text_key = None
    for k in ("text", "word", "caption"):
        if k in sample:
            text_key = k
            break

    if not text_key:
        raise ValueError("Cannot detect word text key. Expected one of: text, word, caption")

    words: List[WordItem] = []
    prev_end = None

    for item in raw:
        text = clean_word(item.get(text_key, ""))
        if not text:
            continue

        start = float(item["start"])
        end = float(item["end"])
        duration = max(0.0, end - start)
        pause_before = 0.0 if prev_end is None else max(0.0, start - prev_end)

        words.append(
            WordItem(
                text=text,
                start=start,
                end=end,
                duration=duration,
                pause_before=pause_before
            )
        )
        prev_end = end

    return words


# ----------------------------
# Scoring
# ----------------------------
def score_word(word: WordItem, position_in_block: int = 0, is_last_before_punct: bool = False) -> int:
    t = word.text
    base = re.sub(r"[।!?.,:;\"'“”‘’]", "", t)

    score = 0

    if base in FINANCE_WORDS:
        score += 15
    if base in EMOTION_WORDS:
        score += 10
    if base in DANGER_WORDS:
        score += 18
    if base in RARE_WORDS:
        score += 6
    if base in QUESTION_WORDS:
        score += 7
    if base in CONTRAST_WORDS:
        score += 8
    if base.isupper() and len(base) >= 2:
        score += 10
    if has_number(base):
        score += 15
    if base in STOPWORDS:
        score -= 6
    if word.pause_before >= LONG_PAUSE_THRESHOLD:
        score += 5
    if is_last_before_punct:
        score += 6
    if position_in_block == 0 and len(base) <= 4:
        score += 2

    return max(score, 0)


def score_phrase(words: List[WordItem]) -> int:
    text = " ".join(w.text for w in words)
    score = 0

    if any(has_number(w.text) for w in words):
        score += 15
    if is_question_text(text):
        score += 12
    if any(re.sub(r"[।!?.,:;]", "", w.text) in DANGER_WORDS for w in words):
        score += 12
    if any(re.sub(r"[।!?.,:;]", "", w.text) in CONTRAST_WORDS for w in words):
        score += 8
    if len(words) <= 3:
        score += 6  # short punch line
    if text.endswith(("।", "!", "?")):
        score += 4

    return score


# ----------------------------
# Segmentation
# ----------------------------
def should_break_block(block_words: List[WordItem], next_word: WordItem) -> bool:
    if not block_words:
        return False

    current_duration = block_words[-1].end - block_words[0].start
    last_word = block_words[-1]

    if len(block_words) >= MAX_BLOCK_WORDS:
        return True

    if ends_sentence(last_word.text) and len(block_words) >= MIN_BLOCK_WORDS:
        return True

    if next_word.pause_before >= VERY_LONG_PAUSE_THRESHOLD:
        return True

    if current_duration >= MAX_BLOCK_DURATION:
        return True

    # Break after meaningful mini-phrases if next pause is decent
    if next_word.pause_before >= LONG_PAUSE_THRESHOLD and len(block_words) >= 2:
        return True

    # Break at strong conclusion words
    stripped_last = re.sub(r"[।!?.,:;]", "", last_word.text)
    if stripped_last in {"हो", "होइन", "मात्र", "अब", "किन", "सुन", "ध्यान"} and len(block_words) >= 2:
        return True

    return False


def build_blocks(words: List[WordItem]) -> List[List[WordItem]]:
    blocks = []
    current = []

    for i, word in enumerate(words):
        if not current:
            current.append(word)
            continue

        current.append(word)

        next_word = words[i + 1] if i + 1 < len(words) else None
        if next_word is None:
            blocks.append(current)
            break

        if should_break_block(current, next_word):
            blocks.append(current)
            current = []

    if current:
        blocks.append(current)

    return blocks


# ----------------------------
# Classification
# ----------------------------
def classify_role(words: List[WordItem]) -> str:
    text = " ".join(w.text for w in words)
    stripped = [re.sub(r"[।!?.,:;]", "", w.text) for w in words]

    if is_question_text(text):
        return "question"
    if any(w in DANGER_WORDS for w in stripped):
        return "warning"
    if any(w in EMOTION_WORDS for w in stripped):
        return "emotional"
    if any(w in CONTRAST_WORDS for w in stripped):
        return "comparison"
    if any(has_number(w.text) for w in words):
        return "fact"
    if len(words) <= 2 and score_phrase(words) >= 18:
        return "hook"

    return "neutral"


def energy_level(words: List[WordItem], role: str) -> str:
    avg_duration = sum(w.duration for w in words) / max(1, len(words))
    phrase_score = score_phrase(words)

    if role in {"hook", "warning", "question"}:
        return "high"
    if phrase_score >= 20 or avg_duration < 0.35:
        return "high"
    if phrase_score >= 10:
        return "medium"
    return "low"


# ----------------------------
# Style planning
# ----------------------------
def choose_layout(role: str, block_index: int) -> str:
    if block_index <= 1 and role in {"hook", "question"}:
        return "center"
    if role in {"warning", "emotional"}:
        return "center_lower"
    return "bottom_center"


def choose_style(role: str, energy: str, text: str) -> Dict[str, Any]:
    base = {
        "font_family": "NotoSansDevanagari-Bold",
        "font_size": 74,
        "stroke": 4,
        "max_width_ratio": 0.82,
        "line_height": 1.0,
        "tracking": 0,
        "preset": "clean_bold"
    }

    if role == "hook":
        base.update({"font_size": 94, "stroke": 5, "preset": "hook_punch"})
    elif role == "warning":
        base.update({"font_size": 88, "stroke": 5, "preset": "danger_punch"})
    elif role == "fact":
        base.update({"font_size": 78, "preset": "clean_finance"})
    elif role == "comparison":
        base.update({"font_size": 80, "preset": "contrast_split"})
    elif role == "question":
        base.update({"font_size": 90, "preset": "question_bold"})
    elif role == "emotional":
        base.update({"font_size": 84, "preset": "emotional_clean"})

    if len(text) > 22:
        base["font_size"] -= 6
    if len(text) > 32:
        base["font_size"] -= 8

    if energy == "high":
        base["stroke"] += 1

    return base


def choose_animation(role: str, energy: str) -> Dict[str, Any]:
    if role == "hook":
        return {"in": "pop", "out": "fade", "emphasis": "pulse"}
    if role == "warning":
        return {"in": "shake_in", "out": "hard_cut", "emphasis": "pulse"}
    if role == "question":
        return {"in": "slide_up", "out": "fade", "emphasis": "bounce"}
    if role == "emotional":
        return {"in": "fade", "out": "fade", "emphasis": "none"}
    if role == "comparison":
        return {"in": "slide_up", "out": "fade", "emphasis": "word_swap"}
    if energy == "high":
        return {"in": "pop", "out": "fade", "emphasis": "pulse"}
    return {"in": "fade", "out": "fade", "emphasis": "none"}


# ----------------------------
# Highlight selection
# ----------------------------
def pick_highlights(words: List[WordItem]) -> List[str]:
    highlights = []

    for idx, w in enumerate(words):
        is_last_before_punct = idx == len(words) - 1 or ends_sentence(w.text)
        w.score = score_word(w, position_in_block=idx, is_last_before_punct=is_last_before_punct)

    sorted_words = sorted(words, key=lambda x: x.score, reverse=True)

    for w in sorted_words[:2]:
        if w.score >= 10:
            clean = re.sub(r"[\"“”'‘’]", "", w.text)
            if clean not in highlights:
                highlights.append(clean)

    return highlights


# ----------------------------
# Build final plan
# ----------------------------
def build_typography_plan(words: List[WordItem]) -> Dict[str, Any]:
    raw_blocks = build_blocks(words)
    blocks_out = []

    for idx, block_words in enumerate(raw_blocks, start=1):
        start = block_words[0].start
        end = max(block_words[-1].end, start + MIN_BLOCK_DURATION)
        text = " ".join(w.text for w in block_words)

        role = classify_role(block_words)
        energy = energy_level(block_words, role)
        layout = choose_layout(role, idx - 1)
        style = choose_style(role, energy, text)
        animation = choose_animation(role, energy)
        highlights = pick_highlights(block_words)

        blocks_out.append(
            asdict(
                CaptionBlock(
                    id=idx,
                    start=safe_round(start),
                    end=safe_round(end),
                    duration=safe_round(end - start),
                    text=text,
                    words=[asdict(w) for w in block_words],
                    role=role,
                    energy=energy,
                    layout=layout,
                    style=style,
                    animation=animation,
                    highlight_words=highlights
                )
            )
        )

    return {
        "meta": {
            "theme": "professional_reel_v1",
            "video_width": 1080,
            "video_height": 1920,
            "safe_margin_x": 80,
            "safe_margin_y": 140
        },
        "blocks": blocks_out
    }


# ----------------------------
# Main
# ----------------------------
def main():
    words = load_timeline(INPUT_FILE)
    plan = build_typography_plan(words)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)

    print(f"✅ Typography plan generated: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()