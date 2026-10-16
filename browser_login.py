"""Open account websites in the same browser used for download cookies."""
import os
from pathlib import Path
import subprocess

SITES={'YouTube':'https://www.youtube.com/','Vimeo':'https://vimeo.com/','Twitch':'https://www.twitch.tv/','Dailymotion':'https://www.dailymotion.com/','Facebook':'https://www.facebook.com/','Instagram':'https://www.instagram.com/','X':'https://x.com/'}
BROWSERS={'chrome':'chrome.exe','edge':'msedge.exe','firefox':'firefox.exe','brave':'brave.exe','chromium':'chromium.exe','opera':'opera.exe','vivaldi':'vivaldi.exe'}


def browser_executable(browser):
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
    subprocess.Popen([executable,SITES[site]],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
