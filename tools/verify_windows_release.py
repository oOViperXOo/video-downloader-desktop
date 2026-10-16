"""Check the exact frozen Windows GUI and its hidden worker pipe transport."""
import os
from pathlib import Path
import subprocess
import sys


def main():
    executable = Path(sys.argv[1]).resolve()
    for arguments, expected in [(['--smoke-test'], 'GUI_READY'), (['--ytdlp', '--version'], None)]:
        result = subprocess.run([str(executable), *arguments],
            env=dict(os.environ, QT_QPA_PLATFORM='windows'),
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=90)
        if result.returncode or 'Traceback' in result.stderr or not result.stdout.strip():
            raise RuntimeError(f'{arguments}: exit={result.returncode}\n{result.stdout}\n{result.stderr}')
        if expected and expected not in result.stdout:
            raise RuntimeError(result.stdout + result.stderr)
        print(f'{arguments[0]}: PASS ({result.stdout.strip()})')
    print(f'Verified native Windows startup and hidden worker output: {executable}')


if __name__ == '__main__':
    main()
