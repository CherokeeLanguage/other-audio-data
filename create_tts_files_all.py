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
import subprocess
import sys


def main():
    if sys.argv[0].strip():
        dir_name: str = os.path.dirname(sys.argv[0])
        if dir_name:
            os.chdir(dir_name)

    exec_list: list[str] = []
    for (dirpath, dirnames, filenames) in os.walk("."):
        for filename in filenames:
            if filename == 'create_tts_files.py':
                exec_list.append(os.path.join(dirpath, filename))

    exec_list.sort()
    for exec_filename in exec_list:
        print()
        print(f"=== {exec_filename}")
        cp: subprocess.CompletedProcess = subprocess.run(["python", exec_filename])
        if cp.returncode > 0:
            raise Exception("Subprocess exited with ERROR")


if __name__ == "__main__":
    main()
