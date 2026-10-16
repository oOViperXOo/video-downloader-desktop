import browser_login
from app import Window,Store
from test_process import app
from PySide6.QtCore import QCoreApplication,QEvent


def test_login_opens_selected_browser_without_shell(monkeypatch):
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
