#!/usr/bin/env python3
import os
import pathlib
import sys
import unicodedata as ud
import warnings
from builtins import list
from shutil import rmtree

import progressbar
import pydub.effects as effects
from pydub import AudioSegment


def main():
    warnings.filterwarnings("ignore")

    skip_speakers: set = set()  # speakers to skip due to audio quality issues (hums, etc)

    if sys.argv[0].strip() != "" and os.path.dirname(sys.argv[0]) != "":
        os.chdir(os.path.dirname(sys.argv[0]))

    output_text: str = "comvoi-all.txt"

    # cleanup any previous runs
    for folder in ["mp3"]:
        rmtree(folder, ignore_errors=True)
    pathlib.Path(".").joinpath("mp3").mkdir(exist_ok=True)

    entries: list = list()
    bad_entries: list = list()

    for lang in ["de", "fr", "nl", "ru", "zh"]:
        with open(pathlib.Path(".").joinpath(lang, "meta.csv")) as f:
            idx: int = 0
            for line in f:
                idx += 1
                fields = line.split("|")
                speaker_no = fields[0]
                speaker = speaker_no + "-" + lang
                if speaker in skip_speakers:
                    continue
                wav = fields[1]
                audio_file: pathlib.Path = pathlib.Path(".").joinpath(lang, "wavs", speaker_no, wav)
                text = ud.normalize('NFC', fields[2]).strip()
                mp3 = pathlib.Path(".").joinpath("mp3", f"{lang}-{speaker}-{idx:09d}.mp3")
                if os.path.exists(audio_file):
                    entries.append((audio_file, speaker, lang, mp3, text))
                else:
                    bad_entries.append((audio_file, speaker, lang, mp3, text))

    print(f"Skipped {len(bad_entries):,} bad entries.")
    print(f"Loaded {len(entries):,} entries.")

    with open("bad-entries.txt", "w") as f:
        idx: int = 0
        for wav, speaker, lang, mp3, text in bad_entries:
            idx += 1
            f.write(f"{idx:06d}|{speaker}|{lang}|{wav}|||{text}|")
            f.write("\n")

    print("Creating mp3s")
    bar = progressbar.ProgressBar(maxval=len(entries))
    bar.start()
    idx: int = 0
    count: int = 0
    shortest_length: float = -1
    longest_length: float = 0.0
    total_length: float = 0.0
    rows: list = []
    for wav, speaker, lang, mp3, text in entries:
        bar.update(count)
        count += 1
        text: str = ud.normalize('NFC', text)
        audio: AudioSegment = AudioSegment.from_file(wav)
        audio = effects.normalize(audio)
        audio = effects.normalize(audio)
        audio = audio.set_channels(1)
        audio = audio.set_frame_rate(22050)
        audio.export(mp3, format="mp3", parameters=["-q:a", "3"])
        total_length += audio.duration_seconds
        if shortest_length < 0 or shortest_length > audio.duration_seconds:
            shortest_length = audio.duration_seconds
        if longest_length < audio.duration_seconds:
            longest_length = audio.duration_seconds
        idx += 1
        rows.append(f"{idx:06d}|{speaker}|{lang}|{mp3}|||{text}|")

    bar.finish()

    with open("assemble-stats.txt", "w") as f:
        print(f"Output {len(rows):,} entries.", file=f)

        print(file=f)

        total_length = int(total_length)
        hours = int(total_length / 3600)
        minutes = int(total_length % 3600 / 60)
        seconds = int(total_length % 60)
        print(f"Total duration: {hours:,}:{minutes:02}:{seconds:02}", file=f)

        shortest_length = int(shortest_length)
        minutes = int(shortest_length / 60)
        seconds = int(shortest_length % 60)
        print(f"Shortest duration: {minutes:,}:{seconds:02}", file=f)

        longest_length = int(longest_length)
        minutes = int(longest_length / 60)
        seconds = int(longest_length % 60)
        print(f"Longest duration: {minutes:,}:{seconds:02}", file=f)

        print(file=f)

    with open(output_text, "w") as f:
        for line in rows:
            f.write(line)
            f.write("\n")

    with open("assemble-stats.txt", "a") as f:
        print(f"All size: {len(rows)}", file=f)
        print(file=f)
        print("Folder:", pathlib.Path(".").resolve().name, file=f)
        print(file=f)

    print("done")
    sys.exit()


if __name__ == "__main__":
    main()
