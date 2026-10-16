"""Open account websites in the same browser used for download cookies."""
import os
from pathlib import Path
import subprocess
import shutil
import sys

SITES={'YouTube':'https://www.youtube.com/','Vimeo':'https://vimeo.com/','Twitch':'https://www.twitch.tv/','Dailymotion':'https://www.dailymotion.com/','Facebook':'https://www.facebook.com/','Instagram':'https://www.instagram.com/','X':'https://x.com/'}
BROWSERS={'chrome':'chrome.exe','edge':'msedge.exe','firefox':'firefox.exe','brave':'brave.exe','chromium':'chromium.exe','opera':'opera.exe','vivaldi':'vivaldi.exe'}
MAC_BROWSERS={'chrome':'Google Chrome.app','edge':'Microsoft Edge.app','firefox':'Firefox.app','brave':'Brave Browser.app','chromium':'Chromium.app','opera':'Opera.app','vivaldi':'Vivaldi.app','safari':'Safari.app'}
LINUX_BROWSERS={'chrome':('google-chrome','google-chrome-stable'),'edge':('microsoft-edge','microsoft-edge-stable'),'firefox':('firefox',),'brave':('brave-browser','brave'),'chromium':('chromium','chromium-browser'),'opera':('opera',),'vivaldi':('vivaldi','vivaldi-stable')}


def browser_choices():
    return list(MAC_BROWSERS if sys.platform=='darwin' else BROWSERS)


def browser_executable(browser):
    if sys.platform=='darwin':
        if browser not in MAC_BROWSERS:raise ValueError('Choose the browser you want to sign in with.')
        for directory in (Path('/Applications'),Path.home()/'Applications',Path('/System/Applications')):
            candidate=directory/MAC_BROWSERS[browser]
            if candidate.is_dir():return str(candidate)
        raise ValueError('This browser was not found. Install it or sign in manually, then Apply the browser login setting.')
    if sys.platform!='win32':
        if browser not in LINUX_BROWSERS:raise ValueError('Choose the browser you want to sign in with.')
        for name in LINUX_BROWSERS[browser]:
            if executable:=shutil.which(name):return executable
        raise ValueError('This browser was not found on PATH. Open it manually, sign in, then Apply the browser login setting.')
    if browser not in BROWSERS:raise ValueError('Choose the browser you want to sign in with.')
    import winreg
    key=r'Software\Microsoft\Windows\CurrentVersion\App Paths'+'\\'+BROWSERS[browser]
    for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY,winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive,key,0,winreg.KEY_READ|view) as entry:
                    path=Path(os.path.expandvars(winreg.QueryValueEx(entry,None)[0].strip('"')))
                    if path.is_file():return str(path)
            except OSError:pass
    raise ValueError('This browser was not found. Open the website in that browser manually, sign in, then Apply the browser login setting.')


def open_sign_in(browser,site):
    if site not in SITES:raise ValueError('Choose a supported account website.')
    executable=browser_executable(browser)
    command=['/usr/bin/open','-a',executable,SITES[site]] if sys.platform=='darwin' else [executable,SITES[site]]
    subprocess.Popen(command,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0) if sys.platform=='win32' else 0)
