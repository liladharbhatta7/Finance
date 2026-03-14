import re
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
        soft_bg = "&H78000000"

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
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        events = []

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

            if block["style"] in {"warning", "question"}:
                events.append(self._fullscreen_tint_event(block["start"], block["end"], "red"))
            elif block["style"] == "harmozi" and (block["id"] % 3 == 0):
                events.append(self._fullscreen_tint_event(block["start"], block["end"], "gold"))
            elif block["style"] == "full" and (block["id"] % 4 == 0):
                events.append(self._fullscreen_tint_event(block["start"], block["end"], "dark"))

            if block["style"] in {"full", "warning", "question"}:
                events.append(self._band_event(block["start"], block["end"], y=800))

            events.append(
                self._dialogue(
                    block["start"],
                    block["end"],
                    style_name,
                    f"{{{pos_tag}{intro}{scale}{extra}}}{line}"
                )
            )

        return header + "\n".join(events)

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