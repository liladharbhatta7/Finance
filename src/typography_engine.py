import re

from src.logger import logger


class TypographyEngine:
    def __init__(self):
        self.max_words = 6
        self.max_duration = 2.2
        self.pause_break = 0.38

        self.highlight_terms = {
            "ipo", "fd", "emi", "sip", "roi", "fomo", "eps",
            "क्रिप्टो", "ब्याज", "महँगी", "कर", "ऋण", "नाफा", "घाटा",
            "जोखिम", "सुरक्षित", "अपराध", "स्क्याम", "सेयर", "पैसा",
            "भ्यालु", "skill", "blockchain", "ब्लकचेन"
        }

        self.warning_terms = {"अपराध", "स्क्याम", "सावधान", "गैरकानुनी", "धोका", "खतरा"}
        self.question_terms = {"के", "किन", "कसरी", "कति", "कस्तो", "हुन्छ?"}
        self.contrast_terms = {"तर", "भने", "खासमा", "बरु", "वास्तवमा"}

    def build(self, timeline_data):
        words = timeline_data.get("words") or []
        scenes = timeline_data.get("scenes") or []

        if not words:
            logger.warning("No word timeline found. Using scene fallback blocks.")
            return self._scene_fallback(scenes)

        normalized = self._normalize(words)
        raw_blocks = self._segment(normalized)
        return self._finalize(raw_blocks, scenes)

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

    def _finalize(self, blocks, scenes):
        out = []

        for i, block in enumerate(blocks):
            text = " ".join(x["word"] for x in block).strip()
            start = round(block[0]["start"], 3)
            end = round(block[-1]["end"], 3)

            role = self._pick_role(text)
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
            })

        return out

    def _scene_fallback(self, scenes):
        out = []
        for i, s in enumerate(scenes):
            text = str(s.get("text", "")).strip()
            if not text:
                continue

            role = self._pick_role(text)
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
            })
        return out

    def _pick_role(self, text):
        clean = self._clean_text(text).lower()
        tokens = clean.split()

        if "?" in text or any(t in self.question_terms for t in tokens):
            return "question"
        if any(t in self.warning_terms for t in tokens):
            return "warning"
        if any(t in self.contrast_terms for t in tokens):
            return "contrast"
        return "normal"

    def _pick_style(self, role, text):
        if role == "warning":
            return "warning"
        if role == "question":
            return "question"
        if role == "contrast":
            return "harmozi"
        if len(text) <= 24:
            return "full"
        return "clean"

    def _pick_highlight(self, block, text):
        m = re.search(r"[\d०-९]+(?:\.\d+)?\s*%|रु\.?\s*[\d०-९,]+|[\d०-९]+(?:\.\d+)?", text, flags=re.I)
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