#!/usr/bin/env bash
"""true" '''\'
set -e
eval "$(conda shell.bash hook)"
conda deactivate
conda activate CherokeeTrainingData
exec python "$0" "$@"
exit $?
''"""
import os
import pathlib
import re
import sys
import unicodedata as ud
import warnings
from builtins import list
from os import listdir
from os.path import isdir
from os.path import isfile
from os.path import join
from shutil import rmtree

import progressbar
import pydub.effects as effects
import torch.hub
from pydub import AudioSegment


def main() -> None:
    mp3_quality: list[str] = ["-q:a", "3"]

    create_22k: bool = False
    create_48k: bool = True

    warnings.filterwarnings("ignore")

    diaz_pipeline = torch.hub.load('pyannote/pyannote-audio', 'dia', device="cuda")

    skip_speakers: set[str] = set()  # speakers to skip due to audio quality issues (hums, etc)
    skip_speakers.add("236-en")

    if sys.argv[0].strip() != "":
        os.chdir(os.path.dirname(sys.argv[0]))

    output_text: str = "cstr-vctk-corpus.txt"
    output_text_48k: str = "cstr-vctk-corpus-48k.txt"

    # cleanup any previous runs
    if create_48k:
        rmtree("mp3-48k", ignore_errors=True)
        pathlib.Path(".").joinpath("mp3-48k").mkdir(exist_ok=True)
    if create_22k:
        rmtree("mp3", ignore_errors=True)
        pathlib.Path(".").joinpath("mp3").mkdir(exist_ok=True)

    txt_dirs: list = [d for d in listdir("txt") if isdir(join("txt", d))]
    txt_dirs.sort()

    entries: list[tuple[str, str, str, str, str]] = list()

    for d in txt_dirs:
        txt_files: list = [f for f in listdir(join("txt", d)) if isfile(join("txt", d, f))]
        txt_files.sort()
        for txt_file in txt_files:
            speaker = "en-" + re.sub(".*?(\\d+)_.*", "\\1", txt_file)
            if speaker in skip_speakers:
                continue
            mp3_file = join("mp3", txt_file.replace(".txt", ".mp3"))
            mp3_48k_file = join("mp3-48k", txt_file.replace(".txt", ".mp3"))
            wav_file = join("wav48", d, txt_file.replace(".txt", ".wav"))
            txt_file = join("txt", d, txt_file)
            text: str
            with open(txt_file, "r") as f:
                for line in f:
                    text = line.strip().replace("|", " ")
                    break
            entries.append((wav_file, speaker, mp3_file, mp3_48k_file, text))

    print(f"Loaded {len(entries):,} entries.")

    bar = progressbar.ProgressBar(maxval=len(entries))
    bar.start()
    idx: int = 0
    count: int = 0
    lang: str = "en"
    shortest_length: float = -1
    longest_length: float = 0.0
    total_length: float = 0.0
    print("Creating mp3s")
    rows: list[str] = []
    rows_48k: list[str] = []
    for wav, speaker, mp3, mp3_48k, text in entries:
        bar.update(count)
        count += 1
        text: str = ud.normalize('NFC', text)
        wav_segment: AudioSegment = AudioSegment.from_file(wav)
        wav_segment = effects.normalize(wav_segment)

        diaz_start: int = len(wav_segment)
        diaz_end: int = 0
        diaz = diaz_pipeline({"audio": wav})
        for turn, _, _ in diaz.itertracks(yield_label=True):
            ts = int(turn.start * 1000 - 10)
            if ts < 0:
                ts = 0
            te = int(turn.end * 1000 + 10)
            if te > len(wav_segment):
                te = len(wav_segment)
            if ts < diaz_start:
                diaz_start = ts
            if te > diaz_end:
                diaz_end = te

        if diaz_end == 0 and diaz_start == len(wav_segment):
            continue

        if diaz_end - diaz_start < 500:
            diaz_start = 0
            diaz_end = len(wav_segment)

        audio: AudioSegment = wav_segment[diaz_start:diaz_end]
        audio = effects.normalize(audio)
        audio = audio.set_channels(1)
        if create_48k:
            audio.set_frame_rate(48000)\
                .export(mp3_48k, format="mp3", parameters=mp3_quality)
        if create_22k:
            audio.set_frame_rate(22050)\
                .export(mp3, format="mp3", parameters=mp3_quality)
        total_length += audio.duration_seconds
        if shortest_length < 0 or shortest_length > audio.duration_seconds:
            shortest_length = audio.duration_seconds
        if longest_length < audio.duration_seconds:
            longest_length = audio.duration_seconds
        idx += 1
        rows.append(f"{idx:06d}|{speaker}|{lang}|{mp3}|||{text}|")
        rows_48k.append(f"{idx:06d}|{speaker}|{lang}|{mp3_48k}|||{text}|")

    bar.finish()

    rows.sort()
    rows_48k.sort()

    with open("assemble-stats.txt", "w") as f:
        print(f"Output {idx:,} entries.", file=f)

        print(file=f)

        total_length = int(total_length)
        minutes = int(total_length / 60)
        seconds = int(total_length % 60)
        print(f"Total duration: {minutes:,}:{seconds:02}", file=f)

        shortest_length = int(shortest_length)
        minutes = int(shortest_length / 60)
        seconds = int(shortest_length % 60)
        print(f"Shortest duration: {minutes:,}:{seconds:02}", file=f)

        longest_length = int(longest_length)
        minutes = int(longest_length / 60)
        seconds = int(longest_length % 60)
        print(f"Longest duration: {minutes:,}:{seconds:02}", file=f)

        print(file=f)

    print("Creating final output files")

    if create_22k:
        with open(output_text, "w") as f:
            for line in rows:
                f.write(line)
                f.write("\n")

    if create_48k:
        with open(output_text_48k, "w") as f:
            for line in rows_48k:
                f.write(line)
                f.write("\n")

    with open("assemble-stats.txt", "a") as f:
        print(f"All size: {len(rows)}", file=f)
        print(file=f)
        print("Folder:", pathlib.Path(".").resolve().name, file=f)
        print(file=f)

    print("done")
    return


if __name__ == "__main__":
    main()
