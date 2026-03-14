from pathlib import Path
import subprocess

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_VIDEO = BASE_DIR / "src" / "input.mp4"
FONT_DIR = BASE_DIR / "src" / "fonts"
OUTPUT_DIR = BASE_DIR / "src" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ASS_FILE = OUTPUT_DIR / "pro_typography.ass"
OUTPUT_VIDEO = OUTPUT_DIR / "pro_typography.mp4"

FONT_FILE = FONT_DIR / "NotoSansDevanagari-Bold.ttf"
LATIN_FONT_FILE = FONT_DIR / "NotoSans-Bold.ttf"  # optional, fallback if present

if not INPUT_VIDEO.exists():
    raise FileNotFoundError(f"Input video not found: {INPUT_VIDEO}")

if not FONT_FILE.exists():
    raise FileNotFoundError(f"Missing font: {FONT_FILE}")


def ffmpeg_path(path: Path) -> str:
    s = str(path.resolve()).replace("\\", "/")
    s = s.replace(":", r"\:")
    s = s.replace("'", r"\'")
    return s


def to_ass_time(seconds: float) -> str:
    cs = int(round(seconds * 100))
    h = cs // 360000
    cs %= 360000
    m = cs // 6000
    cs %= 6000
    s = cs // 100
    cs %= 100
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def esc(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


def dialogue(start, end, style, text):
    return f"Dialogue: 0,{to_ass_time(start)},{to_ass_time(end)},{style},,0,0,0,,{text}"


def make_ass():
    # Colors are ASS BGR hex:
    # &H00BBGGRR
    WHITE = "&H00FFFFFF"
    BLACK = "&H00000000"
    YELLOW = "&H0033CCFF"   # warm gold
    CYAN = "&H00F4E842"     # bright accent
    RED = "&H004040FF"

    lines = []

    header = rf"""[Script Info]
Title: Professional Typography Reel
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
PlayResX: 1080
PlayResY: 1920
YCbCr Matrix: TV.601

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Hook,Noto Sans Devanagari,88,{WHITE},{WHITE},{BLACK},&H78000000,-1,0,0,0,100,100,0,0,1,5,0,5,70,70,120,1
Style: Main,Noto Sans Devanagari,72,{WHITE},{WHITE},{BLACK},&H64000000,-1,0,0,0,100,100,0,0,1,4,0,5,80,80,160,1
Style: Sub,Noto Sans Devanagari,54,{WHITE},{WHITE},{BLACK},&H50000000,-1,0,0,0,100,100,0,0,1,3,0,5,90,90,180,1
Style: CTA,Noto Sans Devanagari,62,{YELLOW},{YELLOW},{BLACK},&H64000000,-1,0,0,0,100,100,0,0,1,4,0,5,80,80,220,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # Scene 1: hook
    lines.append(dialogue(
        0.40, 2.80, "Hook",
        rf"{{\an5\pos(540,520)\fad(120,180)\blur0.6\bord6\shad0\fscx92\fscy92\t(0,260,\fscx100\fscy100)}}तपाईंको पैसा"
    ))
    lines.append(dialogue(
        0.75, 2.80, "Hook",
        rf"{{\an5\pos(540,670)\fad(120,180)\blur0.6\bord6\shad0\1c{YELLOW}\fscx92\fscy92\t(0,260,\fscx108\fscy108)}}हराउँदैछ?"
    ))

    # Scene 2: impact keyword
    lines.append(dialogue(
        3.00, 4.50, "Hook",
        rf"{{\an5\pos(540,960)\fad(100,120)\blur0.5\bord7\shad0\1c{YELLOW}\fscx80\fscy80\t(0,220,\fscx120\fscy120)}}INFLATION"
    ))

    # Scene 3: explanation
    lines.append(dialogue(
        4.75, 8.70, "Main",
        rf"{{\an5\pos(540,980)\fad(120,180)\blur0.4\bord5\shad0\q2}}"
        rf"महँगीले पैसाको real value घटाउँछ।\N"
        rf"केवल saving account मा पैसा राखेर\N"
        rf"धनी बन्न सकिँदैन।"
    ))

    # Scene 4: complex Nepali conjunct test
    lines.append(dialogue(
        9.10, 12.90, "Sub",
        rf"{{\an5\pos(540,960)\fad(120,180)\blur0.3\bord4\shad0\q2}}"
        rf"प्रश्न, दृष्टि, संस्कृति, अर्थव्यवस्था,\N"
        rf"क्षमता, श्रद्धा, प्रज्ञा, सुरक्षित,"
    ))

    # Scene 5: strong statement with color switch
    lines.append(dialogue(
        13.10, 16.60, "Main",
        rf"{{\an5\pos(540,940)\fad(100,180)\blur0.4\bord5\shad0\q2}}"
        rf"FD सुरक्षित हुन सक्छ,\N"
        rf"तर {{\1c{YELLOW}}}wealth creation{{\1c{WHITE}}} को लागि\N"
        rf"त्यो मात्र काफी हुँदैन।"
    ))

    # Scene 6: CTA
    lines.append(dialogue(
        16.90, 20.50, "CTA",
        rf"{{\an5\pos(540,980)\fad(120,220)\blur0.4\bord5\shad0\q2\fscx94\fscy94\t(0,250,\fscx100\fscy100)}}"
        rf"smart सोच राख्नुस्,\Ninvestment सिक्नुस्।"
    ))

    # Small top label
    lines.append(dialogue(
        0.40, 20.50, "Sub",
        rf"{{\an8\pos(540,120)\blur0.2\bord3\shad0\1c{CYAN}\fs34}}FINANCE SHORT"
    ))

    ass_text = header + "\n".join(lines)
    ASS_FILE.write_text(ass_text, encoding="utf-8")


def burn_subtitles():
    ass_path = ffmpeg_path(ASS_FILE)
    fonts_path = ffmpeg_path(FONT_DIR)

    vf = f"subtitles='{ass_path}':fontsdir='{fonts_path}',format=yuv420p"

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(INPUT_VIDEO),
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "19",
        "-c:a", "copy",
        str(OUTPUT_VIDEO),
    ]

    print("Rendering professional typography reel...")
    subprocess.run(cmd, check=True)
    print("Done.")
    print("Output:", OUTPUT_VIDEO)
    print("ASS   :", ASS_FILE)

if __name__ == "__main__":
    make_ass()
    burn_subtitles()