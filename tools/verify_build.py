"""Verify the packaged GUI, including Qt DLL loading, without touching user state."""
import os
from pathlib import Path
import subprocess
import struct
import sys


def main():
    executable = Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1] / 'dist' / 'OrvantaVideoDownloader.exe'
    with executable.open('rb') as binary:
        binary.seek(0x3c)
        pe_offset = struct.unpack('<I', binary.read(4))[0]
        binary.seek(pe_offset + 24 + 68)
        if struct.unpack('<H', binary.read(2))[0] != 2:
            print('Build must use the Windows GUI subsystem (no console).')
            return 1
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    result = subprocess.run([str(executable), '--smoke-test'], env=env,
                            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=90)
    if result.returncode or 'GUI_READY' not in result.stdout or 'Traceback' in result.stderr:
        print(result.stdout + result.stderr)
        return result.returncode or 1
    print('Packaged GUI startup passed (no console, Qt imports, window creation, clean exit).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
