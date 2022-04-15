#!/usr/bin/env bash
"""true" '''\'
set -e
eval "$(conda shell.bash hook)"
conda deactivate
conda activate cherokee-audio-data
exec python "$0" "$@"
exit $?
''"""

import os
import pathlib
import random
import re
import sys
import unicodedata as ud
from builtins import list
from shutil import rmtree

import progressbar
import pydub.effects as effects
from pydub import AudioSegment

from split_audio import detect_sound


def main():
    src_dir: str = "../cstr-vctk-corpus"

    if sys.argv[0].strip():
        dir_name: str = os.path.dirname(sys.argv[0])
        if dir_name:
            os.chdir(dir_name)

    MASTER_TEXT: str = os.path.join(src_dir, "cstr-vctk-corpus-48k.txt")

    rmtree("wav", ignore_errors=True)
    pathlib.Path(".").joinpath("wav").mkdir(exist_ok=True)
    langs: set = set()

    wanted_speakers: set = set()
    speaker_info: dict = dict()
    with open("speaker-info.txt", "r") as f:
        for line in f:
            line.strip()
            if line.startswith("ID"):
                continue
            line = re.sub("(?i)^(\\d+)\\s+(\\d+)\\s+(\\w+)\\s+(\\w+)\\s+(.*?)$",  #
                          "\\1|\\2|\\3|\\4|\\5",  #
                          line)
            line = re.sub("\\s+", " ", line)
            fields = line.split("|")
            accents: str = fields[3]
            region: str = fields[4]
            if "american" not in region.lower() and "american" not in accents.lower():
                continue
            sex: str = fields[2]
            speaker: str = f"en-{fields[0]}"
            wanted_speakers.add(speaker)
            speaker_info[speaker] = (speaker, fields[1], sex.lower(), region, fields[4])
    num_lines: int
    with open(MASTER_TEXT, "r") as f:
        num_lines = sum(1 for line in f)

    print(f"Loading {MASTER_TEXT}")

    bar = progressbar.ProgressBar(maxval=num_lines)
    bar.start()

    bad_speakers: set[str] = set()
    with open(MASTER_TEXT, "r") as f:
        entries: dict = {}
        idx: int = 0
        for line in f:
            idx += 1
            bar.update(idx)
            fields = line.strip().split("|")
            xid: str = fields[0].strip()
            spkr: str = fields[1].strip()
            lang: str = fields[2].strip()
            mp3: str = fields[3].strip()

            if spkr not in wanted_speakers:
                bad_speakers.add(spkr)
                continue
            info = speaker_info[spkr]
            spkr = info[0] + "-" + info[2]

            text: str = ud.normalize("NFC", fields[6].strip())

            if not text.strip():
                continue

            dedupe_key = spkr + "|" + text + "|" + mp3

            entries[dedupe_key] = (xid, spkr, lang, mp3, text)
            langs.add(lang)
    bar.finish()

    print(f"Loaded {len(entries):,} entries with audio and text.")

    bar = progressbar.ProgressBar(maxval=len(entries))
    bar.start()
    shortestLength: float = -1
    longestLength: float = 0.0
    totalLength: float = 0.0
    print("Creating wavs")
    rows: list = []
    idx = 0
    for xid, speaker, lang, mp3, text in entries.values():
        idx += 1
        bar.update(idx)
        wav: str = "wav/" + os.path.splitext(os.path.basename(mp3))[0] + ".wav"
        text: str = ud.normalize('NFC', text)
        mp3_segment: AudioSegment = AudioSegment.from_file(src_dir + "/" + mp3)
        segments: list = detect_sound(mp3_segment)
        if len(segments) > 1:
            mp3_segment = mp3_segment[segments[0][0]:segments[-1][1]]
        audio: AudioSegment = mp3_segment
        audio = effects.normalize(audio)
        audio = audio.set_channels(1)
        audio = audio.set_frame_rate(22050)
        audio.export(wav, format="wav")
        totalLength += audio.duration_seconds
        if shortestLength < 0 or shortestLength > audio.duration_seconds:
            shortestLength = audio.duration_seconds
        if longestLength < audio.duration_seconds:
            longestLength = audio.duration_seconds
        rows.append(f"{xid}|{speaker}|{lang}|{wav}|||{text}|")
    bar.finish()

    with open("stats.txt", "w") as f:
        print(f"Output {len(rows):,} entries.", file=f)

        print(file=f)

        totalLength = int(totalLength)
        hours = int(totalLength / 3600)
        minutes = int(totalLength % 3600 / 60)
        seconds = int(totalLength % 60)
        print(f"Total duration: {hours:,}:{minutes:02}:{seconds:02}", file=f)

        shortestLength = int(shortestLength)
        minutes = int(shortestLength / 60)
        seconds = int(shortestLength % 60)
        print(f"Shortest duration: {minutes:,}:{seconds:02}", file=f)

        longestLength = int(longestLength)
        minutes = int(longestLength / 60)
        seconds = int(longestLength % 60)
        print(f"Longest duration: {minutes:,}:{seconds:02}", file=f)

        print(file=f)

    print("Creating training files")

    # save all copy before shuffling
    with open("all.txt", "w") as f:
        for line in rows:
            f.write(line)
            f.write("\n")

    with open("train.txt", "w") as f:
        f.write("")
    with open("val.txt", "w") as f:
        f.write("")

    trainSize: int = 0
    valSize: int = 0
    for lang in langs:
        subset: list = list()
        for row in rows:
            rlang = row.split("|")[2]
            if rlang != lang:
                continue
            subset.append(row)
        print(f" {lang} length: {len(subset):,}")
        random.Random(len(subset)).shuffle(subset)
        # create train/val sets - splitting up data by language evenly
        trainSize = int(len(subset) * .90)
        valSize = len(subset) - trainSize
        with open("train.txt", "a") as f:
            for line in subset[:trainSize]:
                f.write(line)
                f.write("\n")

        with open("val.txt", "a") as f:
            for line in subset[trainSize:]:
                f.write(line)
                f.write("\n")

    with open("stats.txt", "a") as f:
        print(f"All size: {len(rows):,}", file=f)
        print(f"Train size: {trainSize:,}", file=f)
        print(f"Val size: {valSize:,}", file=f)
        print(file=f)
        print("Folder:", pathlib.Path(".").resolve().name, file=f)
        print(file=f)

    sys.exit()


if __name__ == "__main__":
    main()
