import hashlib
import re

from src.logger import logger


class TypographyEngine:
    def __init__(self):
        self.max_words = 6
        self.max_duration = 2.15
        self.pause_break = 0.34

        self.highlight_terms = {
            "ipo", "fd", "emi", "sip", "roi", "fomo", "eps",
            "क्रिप्टो", "ब्याज", "महँगी", "कर", "ऋण", "नाफा", "घाटा",
            "जोखिम", "सुरक्षित", "अपराध", "स्क्याम", "सेयर", "पैसा",
            "भ्यालु", "skill", "blockchain", "ब्लकचेन", "लगानी",
            "बचत", "कर्जा", "loan", "profit", "loss", "return",
            "inflation", "debt", "share", "market", "bonus", "dividend"
        }

        self.warning_terms = {
            "अपराध", "स्क्याम", "सावधान", "गैरकानुनी", "धोका", "खतरा",
            "गल्ती", "फस्नु", "नोक्सान", "loss", "risk", "warning"
        }

        self.question_terms = {
            "के", "किन", "कसरी", "कति", "कस्तो", "हुन्छ", "हो", "why", "how", "what"
        }

        self.contrast_terms = {
            "तर", "भने", "खासमा", "बरु", "वास्तवमा", "instead", "but", "however"
        }

        self.cta_terms = {
            "follow", "comment", "share", "subscribe", "save",
            "follow गर्नुहोस्", "कमेण्ट", "सेयर", "सेभ", "फलो"
        }

        self.money_terms = {
            "रु", "रुपैयाँ", "रुपैया", "पैसा", "ब्याज", "profit", "loss",
            "return", "roi", "fd", "emi", "loan", "debt", "income"
        }

        self.style_packs = [
            "market_bold",
            "alert_flash",
            "premium_clean",
            "data_pulse",
        ]

    def build(self, timeline_data):
        words = timeline_data.get("words") or []
        scenes = timeline_data.get("scenes") or []

        style_pack = self._choose_style_pack(timeline_data)

        if not words:
            logger.warning("No word timeline found. Using scene fallback blocks.")
            return self._scene_fallback(scenes, style_pack)

        normalized = self._normalize(words)
        raw_blocks = self._segment(normalized)
        return self._finalize(raw_blocks, scenes, style_pack)

    def _choose_style_pack(self, timeline_data):
        joined = []
        for s in timeline_data.get("scenes") or []:
            joined.append(str(s.get("text", "")).strip())

        seed_text = " ".join(joined).strip() or "default"
        digest = hashlib.md5(seed_text.encode("utf-8")).hexdigest()
        idx = int(digest[:8], 16) % len(self.style_packs)
        return self.style_packs[idx]

    def _normalize(self, words):
        out = []
        prev_end = None

        for w in words:
            token = str(w.get("word") or w.get("text") or "").strip()
            if not token:
                continue

            start = float(w.get("start", 0.0))
            end = float(w.get("end", start))
            pause = 0.0 if prev_end is None else max(0.0, start - prev_end)

            out.append({
                "word": token,
                "start": start,
                "end": end,
                "pause_before": pause,
            })
            prev_end = end

        return out

    def _segment(self, words):
        blocks = []
        cur = []

        for i, w in enumerate(words):
            cur.append(w)
            nxt = words[i + 1] if i + 1 < len(words) else None

            if nxt is None:
                blocks.append(cur)
                break

            dur = cur[-1]["end"] - cur[0]["start"]

            if (
                len(cur) >= self.max_words
                or dur >= self.max_duration
                or self._ends_sentence(cur[-1]["word"])
                or nxt["pause_before"] >= self.pause_break
            ):
                blocks.append(cur)
                cur = []

        return [b for b in blocks if b]

    def _finalize(self, blocks, scenes, style_pack):
        out = []

        for i, block in enumerate(blocks):
            text = " ".join(x["word"] for x in block).strip()
            start = round(block[0]["start"], 3)
            end = round(block[-1]["end"], 3)
            role = self._pick_role(text, i)
            style = self._pick_style(role, text)
            highlight = self._pick_highlight(block, text)

            out.append({
                "id": i,
                "start": start,
                "end": end,
                "duration": round(end - start, 3),
                "text": text,
                "style": style,
                "role": role,
                "highlight": highlight,
                "scene_index": self._find_scene_index(start, scenes),
                "style_pack": style_pack,
                "is_numeric_heavy": self._is_numeric_heavy(text),
                "is_money_heavy": self._is_money_heavy(text),
            })

        return out

    def _scene_fallback(self, scenes, style_pack):
        out = []

        for i, s in enumerate(scenes):
            text = str(s.get("text", "")).strip()
            if not text:
                continue

            role = self._pick_role(text, i)

            out.append({
                "id": i,
                "start": float(s.get("start", 0.0)),
                "end": float(s.get("end", 0.0)),
                "duration": float(s.get("duration", 0.0)),
                "text": text,
                "style": self._pick_style(role, text),
                "role": role,
                "highlight": self._pick_highlight([], text),
                "scene_index": s.get("index", i),
                "style_pack": style_pack,
                "is_numeric_heavy": self._is_numeric_heavy(text),
                "is_money_heavy": self._is_money_heavy(text),
            })

        return out

    def _pick_role(self, text, block_index=0):
        clean = self._clean_text(text).lower()
        tokens = clean.split()

        if block_index == 0:
            if "?" in text:
                return "hook_question"
            if self._is_numeric_heavy(text):
                return "hook_stat"
            return "hook"

        if any(t in self.cta_terms for t in tokens):
            return "cta"

        if "?" in text or any(t in self.question_terms for t in tokens):
            return "question"

        if any(t in self.warning_terms for t in tokens):
            return "warning"

        if any(t in self.contrast_terms for t in tokens):
            return "comparison"

        if self._is_numeric_heavy(text):
            return "stat"

        return "normal"

    def _pick_style(self, role, text):
        if role in {"hook", "hook_question", "hook_stat"}:
            return "hook"
        if role == "warning":
            return "warning"
        if role == "question":
            return "question"
        if role == "comparison":
            return "comparison"
        if role == "stat":
            return "stat"
        if role == "cta":
            return "cta"
        if len(text) <= 24:
            return "full"
        return "clean"

    def _pick_highlight(self, block, text):
        m = re.search(
            r"[\d०-९]+(?:\.\d+)?\s*%|रु\.?\s*[\d०-९,]+|[\d०-९]+(?:\.\d+)?",
            text,
            flags=re.I,
        )
        if m:
            return m.group(0).strip()

        for w in block:
            token = self._clean_text(w["word"]).lower()
            if token in self.highlight_terms:
                return w["word"]

        tokens = text.split()
        if tokens:
            last = self._clean_text(tokens[-1]).strip()
            if len(last) >= 3:
                return tokens[-1]

        return None

    def _is_numeric_heavy(self, text):
        return bool(re.search(r"[\d०-९]+(?:\.\d+)?\s*%|रु\.?\s*[\d०-९,]+|[\d०-९]{1,}", text, flags=re.I))

    def _is_money_heavy(self, text):
        clean = self._clean_text(text).lower()
        tokens = set(clean.split())
        return self._is_numeric_heavy(text) or any(t in self.money_terms for t in tokens)

    def _find_scene_index(self, ts, scenes):
        for s in scenes:
            if float(s["start"]) <= ts < float(s["end"]):
                return s.get("index", 0)
        return 0

    def _ends_sentence(self, t):
        return str(t).strip().endswith(("।", "!", "?"))

    def _clean_text(self, t):
        return re.sub(r"[\"'“”‘’(),।!?]", "", str(t)).strip()


typography_engine = TypographyEngine()