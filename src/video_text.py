import re
import hashlib
from pathlib import Path
from PIL import Image

from src.config_loader import config
from src.logger import logger
from src.typography_engine import typography_engine


class VideoTextRenderer:
    def __init__(self):
        self.width = 1080
        self.height = 1920
        self.font_path = str(
            config.root_dir / config.settings.get("FONT_PATH", "src/fonts/NotoSansDevanagari-Bold.ttf")
        )
        self.root_dir = Path(config.root_dir)
        self.font_file = Path(self.font_path)
        self.font_dir = self.font_file.parent
        self.font_family = config.settings.get("FONT_FAMILY", "Noto Sans Devanagari")

    # kept for compatibility with old callers
    def create_text_overlay(self, text, output_path, duration=None):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._save_blank_overlay(output_path)
        return str(output_path)

    def create_ass_file(self, timeline_data, output_path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        blocks = typography_engine.build(timeline_data)
        ass = self._build_ass(blocks)
        output_path.write_text(ass, encoding="utf-8")
        logger.info(f"Typography ASS created: {output_path}")
        return str(output_path)

    def _build_ass(self, blocks):
        white = "&H00FFFFFF"
        black = "&H00000000"
        yellow = "&H0033CCFF"
        cyan = "&H00F0E060"
        red = "&H002A5BFF"
        green = "&H0048D76A"
        soft_bg = "&H78000000"

        style_pack = self._choose_style_pack(blocks)

        header = f"""[Script Info]
Title: Reel Typography
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
PlayResX: {self.width}
PlayResY: {self.height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Full,{self.font_family},104,{white},{white},{black},{soft_bg},-1,0,0,0,100,100,0,0,1,6,0,5,60,60,120,1
Style: Clean,{self.font_family},82,{white},{white},{black},{soft_bg},-1,0,0,0,100,100,0,0,1,5,0,2,70,70,190,1
Style: Harmozi,{self.font_family},100,{white},{white},{black},{soft_bg},-1,0,0,0,100,100,0,0,1,6,0,5,60,60,145,1
Style: Warning,{self.font_family},108,{white},{white},{black},{soft_bg},-1,0,0,0,100,100,0,0,1,6,0,5,60,60,125,1
Style: Question,{self.font_family},106,{white},{white},{black},{soft_bg},-1,0,0,0,100,100,0,0,1,6,0,5,60,60,125,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, Effect, Text
"""

        events = []

        total_end = max((float(b["end"]) for b in blocks), default=0.0)

        # Global background motion graphics only
        events.extend(self._global_pack_events(total_end, style_pack))

        for block in blocks:
            style_name, pos_tag, accent = self._style_map(block["style"], yellow, cyan, red)
            line = self._wrap_for_style(block["text"], block["style"])
            line = self._inline_highlight(line, block.get("highlight"), accent, white)

            intro = r"\fad(80,160)"
            scale = r"\fscx86\fscy86\t(0,120,\fscx112\fscy112)\t(120,240,\fscx100\fscy100)"

            if block["style"] == "warning":
                extra = r"\t(0,120,\fscx118\fscy118)\t(120,220,\fscx100\fscy100)"
                style_name = "Warning"
            elif block["style"] == "question":
                extra = r"\t(0,140,\fscx116\fscy116)\t(140,260,\fscx100\fscy100)"
                style_name = "Question"
            elif block["style"] == "harmozi":
                extra = r"\fsp6\t(0,140,\fsp1)\t(140,280,\fsp0)"
                style_name = "Harmozi"
            elif block["style"] == "full":
                extra = r"\move(540,960,540,910)"
                style_name = "Full"
            else:
                extra = r"\move(540,1460,540,1420)"
                style_name = "Clean"

            # Original tint logic preserved
            if block["style"] in {"warning", "question"}:
                events.append(self._fullscreen_tint_event(block["start"], block["end"], "red"))
            elif block["style"] == "harmozi" and (block["id"] % 3 == 0):
                events.append(self._fullscreen_tint_event(block["start"], block["end"], "gold"))
            elif block["style"] == "full" and (block["id"] % 4 == 0):
                events.append(self._fullscreen_tint_event(block["start"], block["end"], "dark"))

            if block["style"] in {"full", "warning", "question"}:
                events.append(self._band_event(block["start"], block["end"], y=800))

            # New background motion graphics only
            events.extend(self._block_motion_events(block, style_pack, accent, red, green, cyan))

            events.append(
                self._dialogue(
                    block["start"],
                    block["end"],
                    style_name,
                    "{" + f"{pos_tag}{intro}{scale}{extra}" + "}" + line
                )
            )

        return header + "\n".join(events)

    def _choose_style_pack(self, blocks):
        joined = " ".join(str(b.get("text", "")) for b in blocks).strip() or "default"
        digest = hashlib.md5(joined.encode("utf-8")).hexdigest()
        packs = ["market", "alert", "premium", "data"]
        return packs[int(digest[:8], 16) % len(packs)]

    def _global_pack_events(self, total_end, style_pack):
        events = []

        # subtle grid overlay in all packs
        events.extend(self._grid_overlay(0.0, total_end))

        # different pack-level motion look
        if style_pack == "market":
            events.extend(self._bottom_ticker_bars(0.0, total_end, "&H24FFFFFF"))
            events.extend(self._top_progress_bar(0.0, total_end, "&H2033CCFF"))
        elif style_pack == "alert":
            events.extend(self._top_progress_bar(0.0, total_end, "&H202A5BFF"))
        elif style_pack == "premium":
            events.extend(self._top_progress_bar(0.0, total_end, "&H1848D76A"))
        elif style_pack == "data":
            events.extend(self._bottom_ticker_bars(0.0, total_end, "&H20F0E060"))
            events.extend(self._top_progress_bar(0.0, total_end, "&H2033CCFF"))

        return events

    def _block_motion_events(self, block, style_pack, accent, red, green, cyan):
        events = []

        text = str(block.get("text", ""))
        role = block.get("role", "")
        style = block.get("style", "")

        start = float(block["start"])
        end = float(block["end"])

        is_numeric = bool(re.search(r"[\d०-९]+(?:\.\d+)?\s*%|रु\.?\s*[\d०-९,]+|[\d०-९]+(?:\.\d+)?", text, flags=re.I))
        is_warning = style == "warning"
        is_question = style == "question"
        is_contrast = style == "harmozi"

        # arrow sweep for hook-like big text
        if style == "full":
            events.append(self._arrow_sweep(start, min(end, start + 0.8), accent))

        # rising / falling graph lines
        if is_numeric and not is_warning:
            events.append(self._rising_line_chart(start, end, green))
            events.append(self._percentage_pulse(start, min(end, start + 0.9), accent))

        if is_warning:
            events.append(self._falling_line_chart(start, end, red))
            events.append(self._warning_pulse(start, min(end, start + 0.85), red))

        if is_question:
            events.append(self._question_glow(start, min(end, start + 0.75), cyan))

        if is_contrast:
            events.append(self._comparison_divider(start, end, accent))

        if "रु" in text or "पैसा" in text or "ब्याज" in text or "profit" in text.lower() or "loss" in text.lower():
            events.extend(self._rupee_badge(start, min(end, start + 0.8), green))

        return events

    def _style_map(self, style, yellow, cyan, red):
        if style == "warning":
            return "Warning", r"\an5\pos(540,890)\blur0.25\bord6\shad0", red
        if style == "question":
            return "Question", r"\an5\pos(540,910)\blur0.25\bord6\shad0", cyan
        if style == "harmozi":
            return "Harmozi", r"\an5\pos(540,930)\blur0.25\bord6\shad0", yellow
        if style == "full":
            return "Full", r"\an5\pos(540,910)\blur0.25\bord6\shad0", yellow
        return "Clean", r"\an5\pos(540,1420)\blur0.2\bord5\shad0", yellow

    def _wrap_for_style(self, text, style):
        max_chars = 14 if style in {"full", "warning", "question"} else 20
        max_lines = 3 if style in {"full", "warning", "question"} else 2

        words = str(text).split()
        lines = []
        current = []

        for word in words:
            trial = " ".join(current + [word])
            if len(trial) <= max_chars:
                current.append(word)
            else:
                if current:
                    lines.append(" ".join(current))
                current = [word]
                if len(lines) >= max_lines - 1:
                    break

        if current and len(lines) < max_lines:
            lines.append(" ".join(current))

        if not lines:
            return self._ass_escape(text)

        escaped_lines = [self._ass_escape(line) for line in lines]
        return r"\N".join(escaped_lines)

    def _inline_highlight(self, text, highlight, accent, white):
        if not highlight:
            return text

        pattern = re.compile(re.escape(str(highlight).strip()), flags=re.IGNORECASE)

        def repl(match):
            word = self._ass_escape(match.group(0))
            return f"{{\\1c{accent}\\bord7\\blur0.35}}{word}{{\\1c{white}\\bord6\\blur0.25}}"

        return pattern.sub(repl, text, count=1)

    def _band_event(self, start, end, y=840):
        draw = (
            r"{\an7\pos(0,0)\p1\1c&H000000&\1a&H70&\bord0\shad0\fad(60,140)}"
            f"m 40 {y} l 1040 {y} 1040 {y + 260} 40 {y + 260}"
        )
        return self._dialogue(start, end, "Full", draw)

    def _fullscreen_tint_event(self, start, end, mode="dark"):
        if mode == "red":
            color = "&H00201870&"
            alpha = "&H78"
        elif mode == "gold":
            color = "&H00106080&"
            alpha = "&H7A"
        else:
            color = "&H00000000&"
            alpha = "&H88"

        draw = (
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a{alpha}\bord0\shad0\fad(60,140)}}"
            f"m 0 0 l {self.width} 0 {self.width} {self.height} 0 {self.height}"
        )
        return self._dialogue(start, end, "Full", draw)

    # ---------------------------
    # Motion graphics: shapes only
    # ---------------------------

    def _grid_overlay(self, start, end):
        color = "&H180F1722&"
        lines = [
            rf"{{\an7\pos(0,0)\p1\1c{color}\bord0\shad0}}m 120 0 l 122 0 122 {self.height} 120 {self.height}",
            rf"{{\an7\pos(0,0)\p1\1c{color}\bord0\shad0}}m 360 0 l 362 0 362 {self.height} 360 {self.height}",
            rf"{{\an7\pos(0,0)\p1\1c{color}\bord0\shad0}}m 720 0 l 722 0 722 {self.height} 720 {self.height}",
            rf"{{\an7\pos(0,0)\p1\1c{color}\bord0\shad0}}m 0 450 l {self.width} 450 {self.width} 452 0 452",
            rf"{{\an7\pos(0,0)\p1\1c{color}\bord0\shad0}}m 0 980 l {self.width} 980 {self.width} 982 0 982",
            rf"{{\an7\pos(0,0)\p1\1c{color}\bord0\shad0}}m 0 1530 l {self.width} 1530 {self.width} 1532 0 1532",
        ]
        return [self._dialogue(start, end, "Clean", line) for line in lines]

    def _top_progress_bar(self, start, end, color):
        bg = (
            r"{\an7\pos(0,0)\p1\1c&H22000000&\bord0\shad0}"
            "m 90 66 l 990 66 990 82 90 82"
        )
        fill = (
            rf"{{\an7\pos(0,0)\p1\1c{color}\bord0\shad0\move(-840,0,0,0)}}"
            "m 90 66 l 820 66 820 82 90 82"
        )
        return [self._dialogue(start, end, "Clean", bg), self._dialogue(start, end, "Clean", fill)]

    def _bottom_ticker_bars(self, start, end, color):
        bars = []
        y = 1760
        widths = [90, 150, 110, 200, 130, 170]
        x = 40
        for w in widths:
            bars.append(
                rf"{{\an7\move({x+300},0,{x-120},0)\p1\1c{color}\bord0\shad0}}m {x} {y} l {x+w} {y} {x+w} {y+18} {x} {y+18}"
            )
            x += w + 24
        return [self._dialogue(start, end, "Clean", b) for b in bars]

    def _arrow_sweep(self, start, end, color):
        draw = (
            rf"{{\an7\move(-220,565,1260,565)\p1\1c{color}\1a&H38&\bord0\shad0\fad(40,80)}}"
            "m 0 0 l 240 0 240 14 0 14 "
            "m 222 -24 l 280 7 222 38"
        )
        return self._dialogue(start, end, "Clean", draw)

    def _rising_line_chart(self, start, end, color):
        draw = (
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a&H22&\bord2\3c&H00000000&\shad0\fad(50,120)}}"
            "m 128 1450 l 300 1412 472 1428 650 1350 882 1268 "
            "m 854 1242 l 905 1260 874 1300"
        )
        return self._dialogue(start, end, "Clean", draw)

    def _falling_line_chart(self, start, end, color):
        draw = (
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a&H20&\bord2\3c&H00000000&\shad0\fad(50,120)}}"
            "m 126 1268 l 300 1308 472 1288 648 1384 886 1462 "
            "m 854 1436 l 905 1472 846 1492"
        )
        return self._dialogue(start, end, "Clean", draw)

    def _percentage_pulse(self, start, end, color):
        draw = (
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a&H38&\bord0\shad0\fad(30,80)\t(0,180,\fscx128\fscy128)}}"
            "m 920 245 b 980 245 1020 285 1020 345 b 1020 405 980 445 920 445 b 860 445 820 405 820 345 b 820 285 860 245 920 245"
        )
        return self._dialogue(start, end, "Clean", draw)

    def _warning_pulse(self, start, end, color):
        draw = (
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a&H34&\bord0\shad0\fad(30,80)\t(0,180,\fscx120\fscy120)}}"
            "m 916 248 l 982 248 1018 314 982 380 916 380 880 314"
        )
        return self._dialogue(start, end, "Clean", draw)

    def _question_glow(self, start, end, color):
        draw = (
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a&H42&\bord0\shad0\fad(30,80)\t(0,160,\fscx124\fscy124)}}"
            "m 126 236 b 178 236 214 272 214 324 b 214 376 178 412 126 412 b 74 412 38 376 38 324 b 38 272 74 236 126 236"
        )
        return self._dialogue(start, end, "Clean", draw)

    def _comparison_divider(self, start, end, color):
        draw = (
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a&H28&\bord0\shad0\fad(40,100)}}"
            "m 538 600 l 542 600 542 1500 538 1500"
        )
        return self._dialogue(start, end, "Clean", draw)

    def _rupee_badge(self, start, end, color):
        bg = (
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a&H26&\bord0\shad0\fad(40,80)}}"
            "m 84 164 l 154 164 154 234 84 234"
        )
        label = (
            r"{\an7\pos(104,179)\fs44\bord2\shad0\1c&H00FFFFFF&\3c&H00000000&\t(0,120,\fscx110\fscy110)}"
            "रु"
        )
        return [self._dialogue(start, end, "Clean", bg), self._dialogue(start, end, "Clean", label)]

    def _dialogue(self, start, end, style, text):
        return f"Dialogue: 0,{self._to_ass_time(start)},{self._to_ass_time(end)},{style},,0,0,0,,{text}"

    def _to_ass_time(self, seconds):
        cs = int(round(float(seconds) * 100))
        h = cs // 360000
        cs %= 360000
        m = cs // 6000
        cs %= 6000
        s = cs // 100
        cs %= 100
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    def _ass_escape(self, text):
        return str(text).replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")

    def _save_blank_overlay(self, output_path):
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        img.save(output_path)


text_renderer = VideoTextRenderer()