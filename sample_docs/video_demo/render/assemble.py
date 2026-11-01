import json
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg
from manifest import SEGMENTS

ROOT = Path(__file__).parent
AUDIO = ROOT / "audio"
FRAMES = ROOT / "frames"
CLIPS = ROOT / "clips"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

durations = json.loads((ROOT / "durations.json").read_text())


def run(*args):
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *args], check=True)


def make_silent_video_clips():
    """Video-only clips, no audio, so concatenation is a clean stream-copy with no encoder restarts.
    Each clip gets a slow Ken Burns zoom plus a quick dip-to-black at its own in/out edges, so
    cuts read as deliberate transitions instead of a static slideshow, without touching clip
    duration (fades happen inside existing frames, so narration stays perfectly in sync)."""
    for seg in SEGMENTS:
        img = FRAMES / f"{seg['id']}.png"
        out = CLIPS / f"{seg['id']}_video.mp4"
        dur = durations[seg["id"]]
        frames = max(2, round(dur * 25))
        vf = (
            f"zoompan=z='1+0.035*on/{frames - 1}':d={frames}:s=1920x1080:fps=25,"
            f"fade=t=in:st=0:d=0.25,fade=t=out:st={max(dur - 0.25, 0):.3f}:d=0.25"
        )
        run(
            "-i", str(img),
            "-vf", vf,
            "-r", "25",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(out),
        )
        print(f"video clip: {out}")


def concat_video():
    listfile = ROOT / "concat_video_list.txt"
    listfile.write_text(
        "\n".join(f"file '{CLIPS / (s['id'] + '_video.mp4')}'" for s in SEGMENTS)
    )
    out = ROOT / "video_only.mp4"
    run("-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy", str(out))
    print(f"concatenated video: {out}")
    return out


def concat_audio():
    """Concatenate the raw PCM AIFF files directly (identical format across all segments),
    then encode to AAC exactly once. Avoids the per-clip AAC-encoder-restart click that a
    stream-copy concat of separately-encoded AAC clips produces at every cut."""
    listfile = ROOT / "concat_audio_list.txt"
    listfile.write_text(
        "\n".join(f"file '{AUDIO / (s['id'] + '.aiff')}'" for s in SEGMENTS)
    )
    out = ROOT / "narration_master.m4a"
    run(
        "-f", "concat", "-safe", "0", "-i", str(listfile),
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        str(out),
    )
    print(f"concatenated audio: {out}")
    return out


def mux(video_path, audio_path):
    out = ROOT / "walkthrough_no_subs.mp4"
    run(
        "-i", str(video_path), "-i", str(audio_path),
        "-c:v", "copy", "-c:a", "copy",
        "-map", "0:v:0", "-map", "1:a:0",
        "-shortest",
        str(out),
    )
    print(f"muxed: {out}")
    return out


def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


def fmt_ts(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int((t - int(t)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt():
    srt_lines = []
    idx = 1
    cursor = 0.0
    for seg in SEGMENTS:
        dur = durations[seg["id"]]
        sentences = split_sentences(seg["narration"])
        total_chars = sum(len(s) for s in sentences) or 1
        t = cursor
        for sent in sentences:
            frac = len(sent) / total_chars
            s_dur = dur * frac
            start, end = t, min(t + s_dur, cursor + dur)
            srt_lines.append(str(idx))
            srt_lines.append(f"{fmt_ts(start)} --> {fmt_ts(end)}")
            words = sent.split()
            if len(sent) > 60:
                mid = len(words) // 2
                srt_lines.append(" ".join(words[:mid]))
                srt_lines.append(" ".join(words[mid:]))
            else:
                srt_lines.append(sent)
            srt_lines.append("")
            idx += 1
            t = end
        cursor += dur
    (ROOT / "subs.srt").write_text("\n".join(srt_lines))
    print(f"srt: {ROOT / 'subs.srt'} (total {cursor:.1f}s)")


def burn_subs(video_path):
    out = ROOT / "p2g_walkthrough_FINAL.mp4"
    srt = ROOT / "subs.srt"
    style = (
        "FontName=Menlo,FontSize=13,PrimaryColour=&H00F0F0F0,"
        "OutlineColour=&H00101014,BorderStyle=1,Outline=2,Shadow=0,"
        "MarginV=60"
    )
    run(
        "-i", str(video_path),
        "-vf", f"subtitles={srt}:force_style='{style}'",
        "-c:a", "copy",
        str(out),
    )
    print(f"FINAL: {out}")


if __name__ == "__main__":
    make_silent_video_clips()
    video = concat_video()
    audio = concat_audio()
    muxed = mux(video, audio)
    build_srt()
    burn_subs(muxed)
