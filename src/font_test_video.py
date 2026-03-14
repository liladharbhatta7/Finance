from pathlib import Path
import subprocess

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_VIDEO = BASE_DIR / "src" / "input.mp4"
FONT_DIR = BASE_DIR / "src" / "fonts"
OUTPUT_DIR = BASE_DIR / "src" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ASS_FILE = OUTPUT_DIR / "overlay_test.ass"
OUTPUT_VIDEO = OUTPUT_DIR / "overlay_test.mp4"

FONT_FILE = FONT_DIR / "NotoSansDevanagari-Bold.ttf"

if not INPUT_VIDEO.exists():
    raise FileNotFoundError(f"Input video not found: {INPUT_VIDEO}")

if not FONT_FILE.exists():
    raise FileNotFoundError(f"Missing font: {FONT_FILE}")


def ffmpeg_path(path: Path) -> str:
    s = str(path.resolve()).replace("\\", "/")
    s = s.replace(":", r"\:")
    s = s.replace("'", r"\'")
    return s


def make_ass():
    ass_content = r"""[Script Info]
Title: Nepali Complex Paragraph Test
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Sans Devanagari,42,&H00FFFFFF,&H0000FFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,3,0,8,100,100,180,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.50,0:00:15.00,Default,,0,0,0,,नेपाल एउटा सुन्दर देश हो जहाँ संस्कृति, प्रकृति र परम्पराको अद्भुत मिश्रण देख्न पाइन्छ।\Nधेरै मानिसहरू भन्छन् कि सानो देश भए पनि नेपालको इतिहास, समाज र जीवनशैली निकै समृद्ध छ।\Nआजको digital world मा पनि नेपाली युवाहरू technology, startup र online business तिर तीव्र रूपमा अघि बढिरहेका छन्।\Nतर एउटा महत्वपूर्ण प्रश्न भने अझै बाँकी छ — के हाम्रो आर्थिक सोच पर्याप्त रूपमा विकसित भएको छ?\NInflation ले पैसाको real value घटाउँदै जाँदा केवल saving account मा पैसा राखेर मात्र financial freedom सम्भव हुन्छ कि हुँदैन?
"""
    ASS_FILE.write_text(ass_content, encoding="utf-8")
def burn_subtitles():
    ass_path = ffmpeg_path(ASS_FILE)

    # Use the ASS filter directly and force complex shaping
    vf = f"ass='{ass_path}':shaping=complex"

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(INPUT_VIDEO),
        "-vf", vf,
        "-c:v", "libx264",
        "-crf", "20",
        "-preset", "medium",
        "-c:a", "copy",
        str(OUTPUT_VIDEO),
    ]

    print("Burning subtitles...")
    subprocess.run(cmd, check=True)
    print("Done.")
    print("Output:", OUTPUT_VIDEO)


if __name__ == "__main__":
    make_ass()
    burn_subtitles()