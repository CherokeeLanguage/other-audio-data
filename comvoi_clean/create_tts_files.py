#!/usr/bin/env python3
import os
import sys
import unicodedata as ud
import random
import pathlib
from shutil import rmtree

import progressbar
from pydub import AudioSegment
import pydub.effects as effects
from split_audio import detect_sound
from builtins import list

if __name__ == "__main__":

    if sys.argv[0].strip() != "" and os.path.dirname(sys.argv[0]) != "":
        os.chdir(os.path.dirname(sys.argv[0]))

    MASTER_TEXT: str = "comvoi-all.txt"

    rmtree("wav", ignore_errors=True)
    pathlib.Path(".").joinpath("wav").mkdir(exist_ok=True)
    langs: set = set()

    with open(MASTER_TEXT, "r") as f:
        entries: dict = {}
        for line in f:
            fields = line.split("|")
            xid: str = fields[0].strip()
            spkr: str = fields[1].strip()
            lang: str = fields[2].strip()
            mp3: str = fields[3].strip()
            text: str = ud.normalize("NFC", fields[6].strip())
            dedupeKey = spkr + "|" + text + "|" + mp3
            if text == "":
                continue
            entries[dedupeKey] = (xid, spkr, lang, mp3, text)
            langs.add(lang)

    print(f"Loaded {len(entries):,} entries with audio and text.")

    shortestLength: float = -1
    longestLength: float = 0.0
    totalLength: float = 0.0
    print("Creating wavs")

    bar = progressbar.ProgressBar(maxval=len(entries))
    bar.start()

    counter: int = 0
    rows: list = []
    for xid, speaker, lang, mp3, text in entries.values():
        bar.update(counter)
        counter += 1
        wav: str = "wav/" + os.path.splitext(os.path.basename(mp3))[0] + ".wav"
        text: str = ud.normalize('NFC', text)
        mp3_segment: AudioSegment = AudioSegment.from_file(mp3)
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

    # sort then save all copy before shuffling
    rows.sort()
    with open("all.txt", "w") as f:
        for line in rows:
            f.write(line)
            f.write("\n")

    with open("train.txt", "w") as f:
        f.write("")
    with open("val.txt", "w") as f:
        f.write("")

    train_size_all: int = 0
    val_size_all: int = 0
    all_size_all: int = 0

    for lang in langs:
        subset: list = list()
        for row in rows:
            rlang = row.split("|")[2]
            if rlang != lang:
                continue
            subset.append(row)
        all_size_all += len(subset)
        print(f" {lang} length: {len(subset):,}")
        random.Random(len(subset)).shuffle(subset)
        # create train/val sets - splitting up data by language evenly
        trainSize: int = int(len(subset) * .95)
        train_size_all += trainSize
        valSize: int = len(subset) - trainSize
        val_size_all += valSize
        with open("train.txt", "a") as f:
            for line in subset[:trainSize]:
                f.write(line)
                f.write("\n")

        with open("val.txt", "a") as f:
            for line in subset[trainSize:]:
                f.write(line)
                f.write("\n")

        with open(f"stats-{lang}.txt", "a") as f:
            print(f"All size: {len(subset):,d}", file=f)
            print(f"Train size: {trainSize:,d}", file=f)
            print(f"Val size: {valSize:,d}", file=f)
            print(file=f)
            print("Folder:", pathlib.Path(".").resolve().name, file=f)
            print(file=f)

    with open(f"stats-all.txt", "a") as f:
        print(f"All size: {all_size_all:,d}", file=f)
        print(f"Train size: {train_size_all:,d}", file=f)
        print(f"Val size: {val_size_all:,d}", file=f)
        print(file=f)
        print("Folder:", pathlib.Path(".").resolve().name, file=f)
        print(file=f)

    sys.exit()
