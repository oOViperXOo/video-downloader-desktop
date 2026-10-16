"""Prepare native QuickJS, license notices and the macOS icon for POSIX builds."""
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
QUICKJS_COMMIT='6d46d07d04041b40f4f49eaa7fdebe44c314c699'  # upstream v0.17.0

def main():
    if (sys.platform,platform.machine().lower()) not in (('linux','x86_64'),('darwin','arm64')):
        raise SystemExit('Supported builders: Linux x64 or macOS Apple Silicon.')
    output=ROOT/'build/posix';output.mkdir(parents=True,exist_ok=True)
    source=output/'quickjs-source'
    if not source.exists():
        subprocess.run(['git','clone','--depth','1','--branch','v0.17.0','https://github.com/quickjs-ng/quickjs.git',str(source)],check=True)
    actual=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    if actual!=QUICKJS_COMMIT:raise RuntimeError('QuickJS source revision differs from the pinned upstream commit.')
    arguments=['cmake','-S',str(source),'-B',str(source/'build'),'-DCMAKE_BUILD_TYPE=Release','-DBUILD_SHARED_LIBS=OFF']
    if sys.platform=='darwin':arguments+=['-DCMAKE_OSX_DEPLOYMENT_TARGET=15.0']
    subprocess.run(arguments,check=True)
    subprocess.run(['cmake','--build',str(source/'build'),'--config','Release','--target','qjs','--parallel','2'],check=True)
    shutil.copy2(source/'build/qjs',output/'qjs');(output/'qjs').chmod(0o755)
    assert subprocess.check_output([str(output/'qjs'),'--eval','print(1+1)'],text=True).strip()=='2'
    licenses=output/'licenses';licenses.mkdir(exist_ok=True)
    shutil.copy2(source/'LICENSE',licenses/'QuickJS-MIT.txt')
    for name,url in {
        'GPL-2.0.txt':'https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt',
        'GPL-3.0.txt':'https://www.gnu.org/licenses/gpl-3.0.txt',
        'LGPL-3.0.txt':'https://www.gnu.org/licenses/lgpl-3.0.txt',
    }.items():
        with urlopen(url,timeout=30) as response:data=response.read(150000)
        if b'GNU' not in data:raise RuntimeError('Unexpected license response')
        (licenses/name).write_bytes(data)
    (licenses/'SOURCES.txt').write_text(
        'QuickJS-ng v0.17.0: https://github.com/quickjs-ng/quickjs/tree/'+QUICKJS_COMMIT+'\n'
        'FFmpeg: https://ffmpeg.org/download.html\n'
        'aria2: https://github.com/aria2/aria2\n'
        'Qt/PySide: https://download.qt.io/official_releases/\n'
        'Exact tool versions/build flags are recorded in build-info.json. Linux packages come from Ubuntu; macOS packages come from Homebrew.\n',encoding='utf-8')
    if sys.platform=='linux':
        for name in ('ffmpeg','aria2'):
            shutil.copy2(Path('/usr/share/doc')/name/'copyright',licenses/(name+'-copyright.txt'))
    else:
        icons=output/'app.iconset';icons.mkdir(exist_ok=True)
        for size in (16,32,128,256,512):
            for scale,suffix in ((1,''),(2,'@2x')):
                subprocess.run(['sips','-z',str(size*scale),str(size*scale),str(ROOT/'assets/app-icon.png'),
                    '--out',str(icons/f'icon_{size}x{size}{suffix}.png')],check=True,stdout=subprocess.DEVNULL)
        subprocess.run(['iconutil','-c','icns',str(icons),'-o',str(output/'app-icon.icns')],check=True)
    print('Native QuickJS, license notices and platform assets prepared.')

if __name__=='__main__':main()
