import json
import re
import subprocess
from pathlib import Path

from manifest import SEGMENTS

ROOT = Path(__file__).parent
AUDIO = ROOT / "audio"
VOICE = "Daniel"


def say_duration(path: Path) -> float:
    out = subprocess.run(["afinfo", str(path)], capture_output=True, text=True).stdout
    m = re.search(r"estimated duration:\s*([\d.]+)", out)
    return float(m.group(1)) if m else 0.0


def main():
    durations = {}
    for seg in SEGMENTS:
        out_path = AUDIO / f"{seg['id']}.aiff"
        subprocess.run(
            ["say", "-v", VOICE, "-r", "168", "-o", str(out_path), seg["narration"]],
            check=True,
        )
        dur = say_duration(out_path)
        durations[seg["id"]] = dur
        print(f"{seg['id']}: {dur:.2f}s")

    (ROOT / "durations.json").write_text(json.dumps(durations, indent=2))


if __name__ == "__main__":
    main()
