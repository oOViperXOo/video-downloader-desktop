"""Explicit H.264/AAC MP4 copies. Originals are never modified."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading

QUALITY_PRESETS = {
    'small': {'crf': 28, 'preset': 'fast', 'audio_bitrate': '128k', 'estimate_kbps': 1200},
    'balanced': {'crf': 23, 'preset': 'medium', 'audio_bitrate': '192k', 'estimate_kbps': 3000},
    'high': {'crf': 18, 'preset': 'slow', 'audio_bitrate': '256k', 'estimate_kbps': 6500},
}

def estimate_conversion_size(duration, quality='balanced'):
    """Rough planning estimate only; CRF output varies with content/resolution."""
    return int(float(duration) * QUALITY_PRESETS[quality]['estimate_kbps'] * 125) if duration else None

def find_ffmpeg():
    import sys
    bases = [Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)), Path(sys.executable).parent,
             Path(__file__).resolve().parent / 'tools' / 'media']
    for base in bases:
        for rel in ('ffmpeg.exe', 'ffmpeg', 'tools/media/ffmpeg.exe'):
            candidate = base / rel
            if candidate.is_file():
                return str(candidate)
    return shutil.which('ffmpeg')

class Converter:
    def __init__(self, config=None, callback=None):
        self.config = config or {}
        if set(self.config) - {'quality', 'output_dir', 'format'}:
            raise ValueError('Unknown conversion configuration')
        self.quality = self.config.get('quality', 'balanced')
        self.format = self.config.get('format','mp4')
        if self.format not in ('mp4','mp3'):raise ValueError('Copy format must be mp4 or mp3')
        if self.quality not in QUALITY_PRESETS:
            raise ValueError('Conversion quality must be small, balanced or high')
        self.emit = callback or (lambda event: None)
        self.cancelled = False
        self.proc = None
        self.lock = threading.Lock()

    def cancel(self):
        self.cancelled = True
        with self.lock:
            if self.proc is not None and self.proc.poll() is None:
                self.proc.terminate()

    def run(self, source):
        paths, errors = [], []
        temporary, target = None, None
        try:
            source = Path(os.path.abspath(source))
            if not source.is_file():
                raise ValueError('Conversion source must be a file')
            ffmpeg = find_ffmpeg()
            if not ffmpeg:
                raise ValueError('FFmpeg is required for media conversion')
            directory = Path(os.path.abspath(self.config.get('output_dir') or source.parent))
            directory.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(suffix='.'+self.format, prefix='.conversion-', dir=directory)
            os.close(fd)
            duration = None
            probe = str(Path(ffmpeg).with_name('ffprobe.exe' if os.name == 'nt' else 'ffprobe'))
            try:
                measured = subprocess.run([probe, '-v', 'error', '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1', str(source)], capture_output=True,
                    text=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                duration = float(measured.stdout.strip())
            except (OSError, ValueError, subprocess.TimeoutExpired):
                pass
            preset = QUALITY_PRESETS[self.quality]
            command = [ffmpeg, '-hide_banner', '-nostdin', '-y', '-i', str(source), '-map', '0:v:0',
                       '-map', '0:a:0?', '-c:v', 'libx264', '-crf', str(preset['crf']), '-preset', preset['preset'],
                       '-pix_fmt', 'yuv420p', '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2', '-c:a', 'aac',
                       '-b:a', preset['audio_bitrate'], '-movflags', '+faststart', '-progress', 'pipe:1',
                       '-nostats', temporary]
            if self.format=='mp3':
                command=[ffmpeg,'-hide_banner','-nostdin','-y','-i',str(source),'-map','0:a:0','-vn','-c:a','libmp3lame','-b:a','192k','-progress','pipe:1','-nostats',temporary]
            self.emit({'type': 'status', 'status': 'processing', 'message': 'Creating separate '+self.format.upper()+' copy'})
            with self.lock:
                if self.cancelled:
                    raise InterruptedError('Conversion cancelled')
                self.proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding='utf-8', errors='replace',
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            tail = []
            for line in self.proc.stdout:
                tail.append(line.strip())
                tail = tail[-20:]
                if line.startswith('out_time_us=') and duration and duration > 0:
                    try:
                        percent = min(99, max(0, float(line.split('=', 1)[1]) / 1000000 / duration * 100))
                        self.emit({'type': 'progress', 'percent': percent, 'item': None, 'state': 'processing'})
                    except ValueError:
                        pass
            rc = self.proc.wait()
            if self.cancelled:
                raise InterruptedError('Conversion cancelled')
            if rc:
                raise ValueError('FFmpeg conversion failed: ' + '\n'.join(tail)[-1800:])
            # Publish atomically without replacing an existing user file.
            for number in range(1, 10000):
                suffix = '' if number == 1 else ' ' + str(number)
                candidate = directory / (source.stem + ' (converted)' + suffix + '.'+self.format)
                try:
                    if os.name == "nt":
                        os.rename(temporary, candidate)
                    else:
                        os.link(temporary, candidate)
                    target = candidate
                    break
                except FileExistsError:
                    continue
            if target is None:
                raise ValueError('Cannot allocate conversion output filename')
            if os.name != "nt":
                os.unlink(temporary)
            temporary = None
            paths.append(str(target))
            self.emit({'type': 'progress', 'percent': 100, 'filename': str(target), 'item': None})
            self.emit({'type': 'item_done', 'path': str(target), 'item': None})
        except (OSError, ValueError, InterruptedError) as exc:
            if not self.cancelled:
                errors.append({'message': str(exc), 'item': None})
                self.emit({'type': 'error', **errors[-1]})
        finally:
            for path in (temporary, target if not paths else None):
                if path:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
        self.emit({'type': 'status', 'status': 'cancelled' if self.cancelled else 'finished'})
        result = {'type': 'done', 'path': paths[-1] if paths else None, 'paths': paths,
                  'errors': errors, 'skipped': 0, 'returncode': 130 if self.cancelled else (0 if paths else 1),
                  'cancelled': self.cancelled}
        self.emit(result)
        return result
