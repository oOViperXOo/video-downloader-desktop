"""Install/verify/uninstall inside the workspace, without registration or shortcuts."""
from pathlib import Path
import hashlib
import os
import subprocess
import sys
import time
import uuid
import winreg

root=Path(__file__).resolve().parents[1]
setup=Path(sys.argv[1]).resolve();payload=Path(sys.argv[2]).resolve()
target=(root/'test-temp'/('installed QA '+uuid.uuid4().hex)).resolve()
assert target.is_relative_to(root/'test-temp') and not target.exists()
keys=[r'Software\Orvanta\VideoDownloader',r'Software\Microsoft\Windows\CurrentVersion\Uninstall\OrvantaVideoDownloader']
def registry_snapshot():
    result={}
    for key in keys:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key,0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as handle:
                values=[];index=0
                while True:
                    try:values.append(winreg.EnumValue(handle,index));index+=1
                    except OSError:break
                result[key]=values
        except FileNotFoundError:result[key]=None
    return result
before=registry_snapshot()
flags=subprocess.CREATE_NO_WINDOW
# NSIS requires /D to be last and unquoted, even for paths containing spaces.
command=subprocess.list2cmdline([str(setup),'/S','/TESTMODE=1','/MODE=installed'])+' /D='+str(target)
result=subprocess.run(command,creationflags=flags,timeout=240)
assert result.returncode==0,'Installer failed'
assert registry_snapshot()==before,'Test-mode installer changed registration'
count=0;installed_files=[]
for source in payload.rglob('*'):
    if not source.is_file():continue
    destination=target/source.relative_to(payload)
    assert destination.is_file(),f'Missing installed file: {source.name}'
    assert hashlib.sha256(source.read_bytes()).digest()==hashlib.sha256(destination.read_bytes()).digest(),f'Installed file mismatch: {source.name}'
    installed_files.append(destination)
    count+=1
executable=target/'OrvantaVideoDownloader.exe'
for arguments,expected in [(['--smoke-test'],'GUI_READY'),(['--ytdlp','--version'],None)]:
    result=subprocess.run([str(executable),*arguments],capture_output=True,text=True,encoding='utf-8',errors='replace',creationflags=flags,env=dict(os.environ,QT_QPA_PLATFORM='windows'),timeout=90)
    assert result.returncode==0 and result.stdout.strip() and 'Traceback' not in result.stderr,result.stdout+result.stderr
    if expected:assert expected in result.stdout
    print('Installed '+arguments[0]+': PASS')
note=target/'user-created-note.txt';note.write_text('Keep user-created files',encoding='utf-8')
conflict_command=subprocess.list2cmdline([str(setup),'/S','/MODE=portable'])+' /D='+str(target)
assert subprocess.run(conflict_command,creationflags=flags,timeout=30).returncode==2
assert executable.exists() and not (target/'portable.ini').exists()
uninstaller=target/'Uninstall.exe' 
for attempt in range(3):
    result=subprocess.run([str(uninstaller),'/S','/TESTMODE=1'],creationflags=flags,timeout=120)
    assert result.returncode==0,'Uninstaller failed'
    deadline=time.monotonic()+15
    while (executable.exists() or uninstaller.exists()) and time.monotonic()<deadline:time.sleep(.1)
    if not executable.exists() and not uninstaller.exists():break
    # Retry a safe silent abort caused by a transient Windows executable lock.
    # All payload, user-file and registry assertions below remain mandatory.
    if attempt<2 and uninstaller.exists():print('Uninstall not finished; retrying after possible transient file lock',flush=True)
    else:break
assert not executable.exists(),'Uninstaller did not remove application'
assert not uninstaller.exists(),'Uninstaller did not finish'
assert not any(path.exists() for path in installed_files),'Uninstaller left payload files behind'
assert note.read_text(encoding='utf-8')=='Keep user-created files','Uninstaller deleted user files'
assert registry_snapshot()==before,'Test-mode uninstaller changed registration'
print(f'Installer/uninstaller: PASS ({count} payload files verified; user-created file preserved; registry unchanged)')

portable=(root/'test-temp'/('portable QA '+uuid.uuid4().hex)).resolve()
command=subprocess.list2cmdline([str(setup),'/S'])+' /D='+str(portable)
result=subprocess.run(command,creationflags=flags,timeout=240)
assert result.returncode==0
assert sorted(p.name for p in portable.iterdir())==['OrvantaVideoDownloader.exe']
assert registry_snapshot()==before
source_portable=payload.parent/'OrvantaVideoDownloader-Portable.exe'
assert hashlib.sha256(source_portable.read_bytes()).digest()==hashlib.sha256((portable/'OrvantaVideoDownloader.exe').read_bytes()).digest()
result=subprocess.run([str(portable/'OrvantaVideoDownloader.exe'),'--smoke-test'],capture_output=True,text=True,creationflags=flags,timeout=120)
assert result.returncode==0 and 'GUI_READY' in result.stdout, result.stdout+result.stderr
assert 'STATE_DIRECTORY='+str(portable/'Data') not in result.stdout
assert 'AppData' in result.stdout
assert sorted(p.name for p in portable.iterdir())==['OrvantaVideoDownloader.exe']
assert registry_snapshot()==before
print('Portable extraction: PASS (one EXE before/after startup, hash matches, AppData state, no registration or uninstaller)')

legacy=(root/'test-temp'/('legacy branding QA '+uuid.uuid4().hex)).resolve()
legacy.mkdir()
old_executable=legacy/'PreviousDownloader.exe'
old_executable.write_bytes(b'preserve earlier installation')
for mode in ('portable','installed'):
    command=subprocess.list2cmdline([str(setup),'/S','/TESTMODE=1','/MODE='+mode])+' /D='+str(legacy)
    result=subprocess.run(command,creationflags=flags,timeout=240)
    assert result.returncode==2,'Earlier installation must require a separate folder'
    assert list(legacy.iterdir())==[old_executable]
    assert old_executable.read_bytes()==b'preserve earlier installation'
assert registry_snapshot()==before
print('Earlier installation: PASS (both modes refuse mixing brands and preserve old files/registration)')
