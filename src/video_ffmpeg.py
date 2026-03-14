import os
import subprocess

from src.logger import logger
from src.video_text import text_renderer
from src.video_bgm import bgm_selector
from src.video_timeline import timeline_builder
from src.video_sfx import sfx_selector


class VideoEditor:
    def __init__(self):
        self.width = 1080
        self.height = 1920
        self.fps = 30
        self.transition_duration = 0.35

    def assemble_video(self, scenes, audio_path, output_path, temp_dir, category=None):
        if not scenes:
            logger.error("No scenes provided to assemble_video.")
            return False

        timeline_data = timeline_builder.build(scenes, audio_path=audio_path)
        timeline_scenes = timeline_data["scenes"]

        if not timeline_scenes:
            logger.error("No timeline scenes were built.")
            return False

        ass_path = os.path.join(temp_dir, "reel_typography.ass")
        text_renderer.create_ass_file(timeline_data, ass_path)

        inputs = []
        filter_complex = []

        inputs.extend(["-i", audio_path])

        bgm_path = bgm_selector.get_bgm_for_category(category)
        has_bgm = False
        if bgm_path:
            inputs.extend(["-i", bgm_path])
            has_bgm = True

        current_input_idx = 2 if has_bgm else 1
        scene_output_labels = []

        # image scenes only
        for scene in timeline_scenes:
            idx = scene["index"]
            image_path = scene["image_path"]
            duration = float(scene["duration"])

            if not image_path or not os.path.exists(image_path):
                logger.error(f"Scene image missing: {image_path}")
                return False

            inputs.extend(["-loop", "1", "-t", str(duration), "-i", image_path])

            img_idx = current_input_idx
            current_input_idx += 1
            frames = max(1, int(duration * self.fps))

            x_expr = "iw/2-(iw/zoom/2)" if idx % 2 == 0 else "iw/2-(iw/zoom/2)-40"

            filter_complex.append(
                f"[{img_idx}:v]"
                f"scale=2160:-1,"
                f"zoompan=z='min(zoom+0.0016,1.45)':d={frames}:"
                f"x='{x_expr}':y='ih/2-(ih/zoom/2)':s=1080x1920,"
                f"setsar=1,fps={self.fps}"
                f"[v{idx}_bg]"
            )

            filter_complex.append(
                f"[v{idx}_bg]"
                f"drawbox=x=80:y=120:w='min(420,(t/0.35)*420)':h=12:color=yellow@0.85:t=fill:enable='lt(t,0.45)'"
                f"[v{idx}_out]"
            )

            scene_output_labels.append(f"[v{idx}_out]")

        # xfade scenes
        if len(scene_output_labels) == 1:
            final_video_label = scene_output_labels[0]
        else:
            prev_label = scene_output_labels[0]
            current_total = float(timeline_scenes[0]["duration"])

            for i in range(1, len(scene_output_labels)):
                next_label = scene_output_labels[i]
                xfade_out = f"[v_xfade_{i}]"
                offset = max(0.0, current_total - self.transition_duration)

                filter_complex.append(
                    f"{prev_label}{next_label}"
                    f"xfade=transition=fade:duration={self.transition_duration}:offset={offset}"
                    f"{xfade_out}"
                )

                current_total = current_total + float(timeline_scenes[i]["duration"]) - self.transition_duration
                prev_label = xfade_out

            final_video_label = prev_label

        # burn one ASS file on final video
        ass_path_ff = self._ffmpeg_path(ass_path)
        fonts_dir_ff = self._ffmpeg_path(text_renderer.font_dir)

        filter_complex.append(
            f"{final_video_label}"
            f"ass='{ass_path_ff}':fontsdir='{fonts_dir_ff}':shaping=complex"
            f"[v_final]"
        )
        final_video_label = "[v_final]"

        # audio
        sfx_events = sfx_selector.build_events(timeline_data, category=category)
        sfx_input_meta = []

        for event in sfx_events:
            sfx_path = event["path"]
            if sfx_path and os.path.exists(sfx_path):
                inputs.extend(["-i", sfx_path])
                sfx_input_meta.append({
                    "input_idx": current_input_idx,
                    "time": float(event["time"]),
                    "volume": float(event["volume"])
                })
                current_input_idx += 1

        audio_labels = []
        filter_complex.append("[0:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a_narr]")
        audio_labels.append("[a_narr]")

        if has_bgm:
            filter_complex.append(
                "[1:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,"
                "volume=0.08,aloop=loop=-1:size=2147483647[a_bgm]"
            )
            audio_labels.append("[a_bgm]")

        for i, meta in enumerate(sfx_input_meta):
            delay_ms = int(meta["time"] * 1000)
            inp = meta["input_idx"]
            volume = meta["volume"]

            filter_complex.append(
                f"[{inp}:a]"
                f"aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,"
                f"volume={volume},adelay={delay_ms}|{delay_ms}"
                f"[a_sfx_{i}]"
            )
            audio_labels.append(f"[a_sfx_{i}]")

        if len(audio_labels) == 1:
            final_audio_label = audio_labels[0]
        else:
            mix_inputs = "".join(audio_labels)
            filter_complex.append(
                f"{mix_inputs}amix=inputs={len(audio_labels)}:duration=first:dropout_transition=2[a_final]"
            )
            final_audio_label = "[a_final]"

        cmd = (
            ["ffmpeg", "-y"]
            + inputs
            + [
                "-filter_complex", ";".join(filter_complex),
                "-map", final_video_label,
                "-map", final_audio_label,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "20",
                "-pix_fmt", "yuv420p",
                "-r", str(self.fps),
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                output_path,
            ]
        )

        logger.info("Running FFmpeg render with ASS typography...")

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info(f"Video assembled at {output_path}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg failed: {e.stderr.decode(errors='ignore')}")
            return False

    def _ffmpeg_path(self, path):
        s = str(path).replace("\\", "/")
        s = s.replace(":", r"\:")
        s = s.replace("'", r"\'")
        return s


video_editor = VideoEditor()