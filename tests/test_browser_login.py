import browser_login
from app import Window,Store
from test_process import app
from PySide6.QtCore import QCoreApplication,QEvent
from pathlib import Path
import pytest


def test_login_opens_selected_browser_without_shell(monkeypatch):
    monkeypatch.setattr(browser_login.sys,'platform','win32')
    calls=[]
    monkeypatch.setattr(browser_login,'browser_executable',lambda browser: 'C:/Browser/'+browser+'.exe')
    monkeypatch.setattr(browser_login.subprocess,'Popen',lambda args,**kw:calls.append((args,kw)))
    browser_login.open_sign_in('firefox','YouTube')
    assert calls[0][0]==['C:/Browser/firefox.exe','https://www.youtube.com/']
    assert not calls[0][1].get('shell')


def test_login_controls_require_browser_and_do_not_claim_authenticated(tmp_path,monkeypatch):
    opened=[];monkeypatch.setattr(browser_login,'open_sign_in',lambda *args:opened.append(args))
    w=Window(Store(tmp_path));w.open_preferences();assert not w.login_button.isEnabled()
    w.cookies_browser.setCurrentText('firefox');w.login_button.click()
    assert opened==[('firefox','YouTube')] and 'Complete sign-in' in w.login_status.text()
    assert w.effective_config()['cookies_browser']=='none'
    w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def test_linux_finds_selected_browser_and_launches_it(monkeypatch):
    monkeypatch.setattr(browser_login.sys,'platform','linux')
    monkeypatch.setattr(browser_login.shutil,'which',lambda name:'/usr/bin/google-chrome-stable' if name=='google-chrome-stable' else None)
    calls=[];monkeypatch.setattr(browser_login.subprocess,'Popen',lambda args,**kw:calls.append((args,kw)))
    browser_login.open_sign_in('chrome','YouTube')
    assert calls[0][0]==['/usr/bin/google-chrome-stable','https://www.youtube.com/']
    assert calls[0][1]['creationflags']==0


def test_macos_opens_selected_bundle_and_offers_safari(monkeypatch):
    monkeypatch.setattr(browser_login.sys,'platform','darwin')
    monkeypatch.setattr(Path,'is_dir',lambda path:path.as_posix().endswith('/Applications/Firefox.app'))
    calls=[];monkeypatch.setattr(browser_login.subprocess,'Popen',lambda args,**kw:calls.append(args))
    browser_login.open_sign_in('firefox','YouTube')
    assert calls[0]==['/usr/bin/open','-a',str(Path('/Applications/Firefox.app')),'https://www.youtube.com/']
    assert 'safari' in browser_login.browser_choices()


@pytest.mark.parametrize('system',['linux','darwin'])
def test_missing_browser_does_not_open_another_browser(system,monkeypatch):
    monkeypatch.setattr(browser_login.sys,'platform',system)
    monkeypatch.setattr(browser_login.shutil,'which',lambda name:None)
    monkeypatch.setattr(Path,'is_dir',lambda path:False)
    monkeypatch.setattr(browser_login.subprocess,'Popen',lambda *args,**kw:pytest.fail('Wrong browser launched'))
    with pytest.raises(ValueError,match='not found'):browser_login.open_sign_in('firefox','YouTube')
