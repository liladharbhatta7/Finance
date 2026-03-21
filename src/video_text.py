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
        if not blocks:
            return self._empty_ass()

        pack = blocks[0].get("style_pack", "market_bold")
        palette = self._palette_for_pack(pack)

        header = self._header(palette)
        events = []

        total_end = max(float(b["end"]) for b in blocks)

        # whole-video ambient overlays by style pack
        events.extend(self._global_pack_events(pack, total_end, palette))

        for block in blocks:
            style_name, pos_tag, accent = self._style_map(block["style"], palette)
            line = self._wrap_for_style(block["text"], block["style"])
            line = self._inline_highlight(line, block.get("highlight"), accent, palette["white"])

            text_tag = self._text_animation_tag(block, pos_tag, pack)

            # pack-aware motion graphics
            events.extend(self._block_motion_events(block, pack, palette))

            events.append(
                self._dialogue(
                    block["start"],
                    block["end"],
                    style_name,
                    f"{{{text_tag}}}{line}"
                )
            )

        return header + "\n".join(events)

    def _empty_ass(self):
        return self._header(self._palette_for_pack("market_bold"))

    def _header(self, palette):
        white = palette["white"]
        black = palette["black"]
        soft_bg = palette["soft_bg"]

        return f"""[Script Info]
Title: Reel Typography
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
PlayResX: {self.width}
PlayResY: {self.height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Hook,{self.font_family},122,{white},{white},{black},{soft_bg},-1,0,0,0,100,100,0,0,1,6,0,5,55,55,110,1
Style: Stat,{self.font_family},116,{white},{white},{black},{soft_bg},-1,0,0,0,100,100,0,0,1,6,0,5,55,55,118,1
Style: Warning,{self.font_family},118,{white},{white},{black},{soft_bg},-1,0,0,0,100,100,0,0,1,6,0,5,55,55,118,1
Style: Question,{self.font_family},114,{white},{white},{black},{soft_bg},-1,0,0,0,100,100,0,0,1,6,0,5,55,55,118,1
Style: Comparison,{self.font_family},108,{white},{white},{black},{soft_bg},-1,0,0,0,100,100,0,0,1,6,0,5,60,60,128,1
Style: Full,{self.font_family},112,{white},{white},{black},{soft_bg},-1,0,0,0,100,100,0,0,1,6,0,5,58,58,120,1
Style: Clean,{self.font_family},88,{white},{white},{black},{soft_bg},-1,0,0,0,100,100,0,0,1,5,0,2,70,70,182,1
Style: CTA,{self.font_family},110,{white},{white},{black},{soft_bg},-1,0,0,0,100,100,0,0,1,6,0,5,60,60,140,1
Style: Tiny,{self.font_family},48,{white},{white},{black},{soft_bg},-1,0,0,0,100,100,0,0,1,3,0,1,40,40,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def _palette_for_pack(self, pack):
        palettes = {
            "market_bold": {
                "white": "&H00F8F8F8",
                "black": "&H00000000",
                "soft_bg": "&H72000000",
                "accent": "&H0033CCFF",     # gold-ish
                "accent2": "&H006ED8FF",    # warm yellow
                "green": "&H0048D76A",
                "red": "&H003050FF",
                "cyan": "&H00F0E060",
                "grid": "&H22151A28",
                "ticker_bg": "&H50000000",
            },
            "alert_flash": {
                "white": "&H00FFFFFF",
                "black": "&H00000000",
                "soft_bg": "&H76000000",
                "accent": "&H002A5BFF",
                "accent2": "&H0033CCFF",
                "green": "&H0048D76A",
                "red": "&H002A5BFF",
                "cyan": "&H00E5D34F",
                "grid": "&H221A1628",
                "ticker_bg": "&H5A000000",
            },
            "premium_clean": {
                "white": "&H00F7F7F4",
                "black": "&H00000000",
                "soft_bg": "&H66000000",
                "accent": "&H0048C8F3",
                "accent2": "&H0030B0FF",
                "green": "&H004CC26E",
                "red": "&H003A6BFF",
                "cyan": "&H00DCD28A",
                "grid": "&H18141620",
                "ticker_bg": "&H44000000",
            },
            "data_pulse": {
                "white": "&H00FFFFFF",
                "black": "&H00000000",
                "soft_bg": "&H70000000",
                "accent": "&H00F0E060",
                "accent2": "&H0033CCFF",
                "green": "&H0048D76A",
                "red": "&H003050FF",
                "cyan": "&H00E8C85A",
                "grid": "&H20141A24",
                "ticker_bg": "&H52000000",
            },
        }
        return palettes.get(pack, palettes["market_bold"])

    def _style_map(self, style, palette):
        accent = palette["accent"]
        cyan = palette["cyan"]
        red = palette["red"]

        if style == "warning":
            return "Warning", r"\an5\pos(540,905)\blur0.25\bord6\shad0", red
        if style == "question":
            return "Question", r"\an5\pos(540,915)\blur0.25\bord6\shad0", cyan
        if style == "comparison":
            return "Comparison", r"\an5\pos(540,930)\blur0.25\bord6\shad0", accent
        if style == "stat":
            return "Stat", r"\an5\pos(540,915)\blur0.25\bord6\shad0", accent
        if style == "hook":
            return "Hook", r"\an5\pos(540,900)\blur0.25\bord6\shad0", accent
        if style == "cta":
            return "CTA", r"\an5\pos(540,1260)\blur0.25\bord6\shad0", accent
        if style == "full":
            return "Full", r"\an5\pos(540,920)\blur0.25\bord6\shad0", accent
        return "Clean", r"\an5\pos(540,1410)\blur0.2\bord5\shad0", accent

    def _text_animation_tag(self, block, pos_tag, pack):
        style = block["style"]

        base_intro = r"\fad(70,140)"
        pop = r"\fscx84\fscy84\t(0,120,\fscx110\fscy110)\t(120,240,\fscx100\fscy100)"

        if style == "hook":
            extra = r"\t(0,100,\fscx118\fscy118)\t(100,220,\fscx100\fscy100)\fsp2"
        elif style == "warning":
            extra = r"\t(0,120,\fscx120\fscy120)\t(120,220,\fscx100\fscy100)"
        elif style == "question":
            extra = r"\t(0,110,\fscx116\fscy116)\t(110,240,\fscx100\fscy100)"
        elif style == "comparison":
            extra = r"\move(540,980,540,930)\fsp4\t(0,140,\fsp1)"
        elif style == "stat":
            extra = r"\move(540,965,540,915)\fsp2"
        elif style == "cta":
            extra = r"\move(540,1320,540,1260)\fsp2"
        elif style == "full":
            extra = r"\move(540,970,540,920)"
        else:
            extra = r"\move(540,1460,540,1410)"

        if pack == "premium_clean":
            extra += r"\blur0.1"
        elif pack == "alert_flash":
            extra += r"\t(0,90,\alpha&H10&)\t(90,180,\alpha&H00&)"
        elif pack == "data_pulse":
            extra += r"\fsp2\t(0,120,\fsp0)"

        return f"{pos_tag}{base_intro}{pop}{extra}"

    def _wrap_for_style(self, text, style):
        if style in {"hook", "warning", "question", "stat"}:
            max_chars = 14
            max_lines = 3
        elif style in {"comparison", "full"}:
            max_chars = 16
            max_lines = 3
        elif style == "cta":
            max_chars = 18
            max_lines = 2
        else:
            max_chars = 20
            max_lines = 2

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
            return f"{{\\1c{accent}\\bord8\\blur0.45}}{word}{{\\1c{white}\\bord6\\blur0.25}}"

        return pattern.sub(repl, text, count=1)

    def _global_pack_events(self, pack, total_end, palette):
        events = []

        events.append(self._grid_overlay(0.0, total_end, palette["grid"]))

        if pack in {"market_bold", "data_pulse"}:
            events.append(self._top_corner_label(0.0, total_end, "FINANCE SHORT", palette["accent"]))
            events.append(self._ticker_strip(0.0, total_end, palette))
        elif pack == "alert_flash":
            events.append(self._top_corner_label(0.0, total_end, "MARKET ALERT", palette["red"]))
            events.append(self._progress_indicator(0.0, total_end, palette["accent2"]))
        elif pack == "premium_clean":
            events.append(self._top_corner_label(0.0, total_end, "SMART MONEY", palette["accent"]))
            events.append(self._progress_indicator(0.0, total_end, palette["accent"]))

        return events

    def _block_motion_events(self, block, pack, palette):
        events = []

        role = block["role"]
        style = block["style"]
        start = float(block["start"])
        end = float(block["end"])
        highlight = block.get("highlight")

        # Background band behind strong blocks
        if style in {"hook", "warning", "question", "stat", "comparison", "full"}:
            events.append(self._band_event(start, end, y=790 if style != "cta" else 1110))

        # Pack-aware tint pulses
        if style == "warning":
            events.append(self._fullscreen_tint_event(start, end, palette["red"], "&H78"))
            events.append(self._warning_pulse(start, end, palette["red"]))
        elif style == "question":
            events.append(self._fullscreen_tint_event(start, end, palette["cyan"], "&H84"))
        elif style == "hook" and pack in {"market_bold", "alert_flash"}:
            events.append(self._fullscreen_tint_event(start, end, palette["accent"], "&H8C"))
        elif style == "comparison" and pack == "premium_clean":
            events.append(self._fullscreen_tint_event(start, end, palette["accent"], "&H92"))

        # finance overlays
        if block.get("is_numeric_heavy"):
            events.append(self._stat_badge(start, end, highlight or "DATA", palette["accent"]))
            events.append(self._percentage_pulse(start, end, palette["accent2"]))

        if block.get("is_money_heavy"):
            events.append(self._rupee_badge(start, end, palette["green"]))

        if role in {"hook_stat", "stat"}:
            events.append(self._rising_line_chart(start, end, palette["green"], pack))

        if role == "warning":
            events.append(self._falling_line_chart(start, end, palette["red"], pack))

        if role == "comparison":
            events.append(self._comparison_divider(start, end, palette["accent"]))

        if role in {"hook", "hook_question", "hook_stat"}:
            events.append(self._arrow_sweep(start, end, palette["accent"]))

        if role == "cta":
            events.append(self._cta_bar(start, end, palette["accent"]))

        return events

    def _band_event(self, start, end, y=840):
        draw = (
            r"{\an7\pos(0,0)\p1\1c&H000000&\1a&H68&\bord0\shad0\fad(50,120)}"
            f"m 42 {y} l 1038 {y} 1038 {y + 278} 42 {y + 278}"
        )
        return self._dialogue(start, end, "Full", draw)

    def _grid_overlay(self, start, end, color):
        cmds = [
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a&H00&\bord0\shad0}}m 120 0 l 122 0 122 {self.height} 120 {self.height}",
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a&H00&\bord0\shad0}}m 360 0 l 362 0 362 {self.height} 360 {self.height}",
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a&H00&\bord0\shad0}}m 720 0 l 722 0 722 {self.height} 720 {self.height}",
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a&H00&\bord0\shad0}}m 0 430 l {self.width} 430 {self.width} 432 0 432",
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a&H00&\bord0\shad0}}m 0 980 l {self.width} 980 {self.width} 982 0 982",
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a&H00&\bord0\shad0}}m 0 1510 l {self.width} 1510 {self.width} 1512 0 1512",
        ]
        return "\n".join(self._dialogue(start, end, "Tiny", c) for c in cmds)

    def _ticker_strip(self, start, end, palette):
        bg = (
            rf"{{\an7\pos(0,0)\p1\1c{palette['ticker_bg']}\1a&H18&\bord0\shad0}}"
            f"m 0 1730 l {self.width} 1730 {self.width} 1816 0 1816"
        )
        text = (
            rf"{{\an5\move(1260,1772,-180,1772)\fs42\bord2\shad0\1c{palette['white']}\3c{palette['black']}}}"
            "MARKET • RETURN • FD • SIP • LOAN • PROFIT • RISK • ROI • SHARE • SAVINGS"
        )
        return self._dialogue(start, end, "Tiny", bg) + "\n" + self._dialogue(start, end, "Tiny", text)

    def _top_corner_label(self, start, end, text, color):
        draw = (
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a&H20&\bord0\shad0\fad(60,140)}}"
            "m 46 62 l 386 62 386 128 46 128"
        )
        label = (
            rf"{{\an7\pos(68,84)\fs38\bord2\shad0\1c&H00FFFFFF&\3c&H00000000&\fad(60,140)}}"
            f"{self._ass_escape(text)}"
        )
        return self._dialogue(start, end, "Tiny", draw) + "\n" + self._dialogue(start, end, "Tiny", label)

    def _progress_indicator(self, start, end, color):
        bg = (
            rf"{{\an7\pos(0,0)\p1\1c&H00202020&\1a&H40&\bord0\shad0}}"
            "m 80 1656 l 1000 1656 1000 1676 80 1676"
        )
        fill = (
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a&H15&\bord0\shad0\t(0,500,\fscx100)}}"
            "m 80 1656 l 880 1656 880 1676 80 1676"
        )
        return self._dialogue(start, end, "Tiny", bg) + "\n" + self._dialogue(start, end, "Tiny", fill)

    def _fullscreen_tint_event(self, start, end, color, alpha):
        draw = (
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a{alpha}\bord0\shad0\fad(60,120)}}"
            f"m 0 0 l {self.width} 0 {self.width} {self.height} 0 {self.height}"
        )
        return self._dialogue(start, end, "Tiny", draw)

    def _arrow_sweep(self, start, end, color):
        draw = (
            rf"{{\an7\move(-180,560,1260,560)\p1\1c{color}\1a&H35&\bord0\shad0\fad(40,80)}}"
            "m 0 0 l 240 0 240 14 0 14 "
            "m 226 -26 l 280 7 226 40"
        )
        return self._dialogue(start, min(end, start + 0.85), "Tiny", draw)

    def _rising_line_chart(self, start, end, color, pack):
        y0 = 1430 if pack != "premium_clean" else 1460
        draw = (
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a&H20&\bord2\3c&H00000000&\shad0\fad(50,120)}}"
            f"m 120 {y0} l 280 {y0-40} 470 {y0-18} 660 {y0-110} 880 {y0-190} "
            f"m 850 {y0-208} l 905 {y0-188} 872 {y0-150}"
        )
        return self._dialogue(start, end, "Tiny", draw)

    def _falling_line_chart(self, start, end, color, pack):
        y0 = 1430 if pack != "premium_clean" else 1460
        draw = (
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a&H18&\bord2\3c&H00000000&\shad0\fad(50,120)}}"
            f"m 120 {y0-180} l 300 {y0-135} 470 {y0-155} 650 {y0-42} 885 {y0+40} "
            f"m 858 {y0+10} l 900 {y0+48} 846 {y0+72}"
        )
        return self._dialogue(start, end, "Tiny", draw)

    def _stat_badge(self, start, end, text, color):
        bg = (
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a&H18&\bord0\shad0\fad(40,100)}}"
            "m 800 150 l 1005 150 1005 226 800 226"
        )
        label = (
            rf"{{\an7\pos(825,171)\fs40\bord2\shad0\1c&H00FFFFFF&\3c&H00000000&\t(0,120,\fscx108\fscy108)}}"
            f"{self._ass_escape(str(text)[:18])}"
        )
        return self._dialogue(start, end, "Tiny", bg) + "\n" + self._dialogue(start, end, "Tiny", label)

    def _rupee_badge(self, start, end, color):
        bg = (
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a&H24&\bord0\shad0\fad(40,100)}}"
            "m 86 154 l 162 154 162 230 86 230"
        )
        label = (
            r"{\an7\pos(109,172)\fs46\bord2\shad0\1c&H00FFFFFF&\3c&H00000000&\t(0,120,\fscx112\fscy112)}"
            "रु"
        )
        return self._dialogue(start, end, "Tiny", bg) + "\n" + self._dialogue(start, end, "Tiny", label)

    def _percentage_pulse(self, start, end, color):
        ring = (
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a&H38&\bord0\shad0\fad(30,80)\t(0,180,\fscx130\fscy130)}}"
            "m 936 280 b 996 280 1038 322 1038 382 b 1038 442 996 484 936 484 b 876 484 834 442 834 382 b 834 322 876 280 936 280"
        )
        return self._dialogue(start, min(end, start + 0.8), "Tiny", ring)

    def _warning_pulse(self, start, end, color):
        draw = (
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a&H30&\bord0\shad0\fad(30,80)\t(0,160,\fscx122\fscy122)}}"
            "m 920 280 l 980 280 1016 342 980 404 920 404 884 342"
        )
        return self._dialogue(start, min(end, start + 0.75), "Tiny", draw)

    def _comparison_divider(self, start, end, color):
        line = (
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a&H26&\bord0\shad0\fad(40,100)}}"
            f"m 538 590 l 542 590 542 1510 538 1510"
        )
        return self._dialogue(start, end, "Tiny", line)

    def _cta_bar(self, start, end, color):
        draw = (
            rf"{{\an7\pos(0,0)\p1\1c{color}\1a&H20&\bord0\shad0\fad(40,100)}}"
            "m 140 1520 l 940 1520 940 1588 140 1588"
        )
        return self._dialogue(start, end, "Tiny", draw)

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