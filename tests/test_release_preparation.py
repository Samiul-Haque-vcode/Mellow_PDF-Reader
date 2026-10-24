"""Release identity policy, preserved document tabs and optional caption layout."""
import importlib.util
from pathlib import Path
from subprocess import CalledProcessError
import pytest
from PySide6.QtCore import Qt,QPoint,QEvent
from PySide6.QtTest import QTest
from test_reader import app,pdf,wait
from mellow.app import Window
from mellow.storage import Store
from mellow.settings import SettingsDialog
from mellow.caption import caption_space,supported,native_flags,CAPTION_CONTROLS


def load(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).resolve().parents[1]/'packaging'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_caption_setting_waits_for_save_and_restart(app,tmp_path):
    store=Store(tmp_path/'caption.db')
    dialog=SettingsDialog(store)
    dialog.caption_tabs.setChecked(True)
    assert store.get('caption_tabs') is None
    w=Window(store,restore=False);w.show();wait(app)
    old=w.caption_tabs.enabled
    w.apply_settings(dialog.values())
    assert store.get('caption_tabs') is True and w.caption_tabs.enabled==old
    dialog.reset_appearance();assert dialog.caption_tabs.isChecked()
    w.close()
    reopened=Window(store,restore=False);reopened.show();wait(app)
    assert reopened.caption_tabs.enabled==supported()
    assert not reopened.windowFlags() & Qt.WindowType.FramelessWindowHint
    reopened.close()


def test_caption_reserves_buttons_and_releases_space_in_fullscreen():
    assert caption_space(32)==(32,152)
    assert caption_space(40,210)==(40,210)
    assert caption_space(32,152,True)==(0,0)


@pytest.mark.parametrize('enabled',[False,True])
def test_caption_tabs_claim_the_safe_area_only_when_enabled(app,tmp_path,monkeypatch,enabled):
    from mellow import caption
    monkeypatch.setattr(caption,'supported',lambda:True)
    store=Store(tmp_path/'safe-area.db');store.set('caption_tabs',enabled)
    w=Window(store,restore=False);w.show();wait(app)
    # QWidget enables this during native creation unless explicitly opted out.
    # Offscreen has zero safe margins, so verify the policy as well as geometry.
    attribute=Qt.WidgetAttribute.WA_ContentsMarginsRespectsSafeArea
    assert w.testAttribute(attribute)==(not enabled)
    if enabled:
        assert w.tabstrip.mapTo(w,QPoint()).y()==0
        w.fullscreen();wait(app);w.fullscreen();wait(app)
        assert not w.testAttribute(attribute)
        assert w.tabstrip.mapTo(w,QPoint()).y()==0
    w.close()


def test_native_caption_masks_retain_high_control_bits():
    if not hasattr(Qt.WindowType,'ExpandedClientAreaHint'):
        pytest.skip('Qt 6.8 uses the standard-caption fallback')
    unrelated=Qt.WindowType.WindowStaysOnTopHint
    original=int(unrelated)|int(Qt.WindowType.WindowTitleHint)|int(Qt.WindowType.NoTitleBarBackgroundHint)
    for fullscreen in (False,True):
        flags=int(native_flags(Qt.WindowType(original),fullscreen))
        assert flags & int(CAPTION_CONTROLS)==int(CAPTION_CONTROLS)
        assert flags & int(unrelated)
        assert not flags & int(Qt.WindowType.WindowTitleHint)
        assert bool(flags & int(Qt.WindowType.ExpandedClientAreaHint))== (not fullscreen)
        assert flags & int(Qt.WindowType.NoTitleBarBackgroundHint)


@pytest.mark.parametrize('event_type',[QEvent.Type.StyleChange,QEvent.Type.PaletteChange,
                                    QEvent.Type.ThemeChange,QEvent.Type.WinIdChange,
                                    QEvent.Type.WindowTitleChange])
def test_caption_recovers_flags_after_late_platform_sync(app,tmp_path,monkeypatch,event_type):
    from mellow import caption
    monkeypatch.setattr(caption,'supported',lambda:True)
    w=Window(Store(tmp_path/'late-caption.db'),restore=False)
    w.showMaximized();wait(app)
    # Simulate QWidget/platform flag normalization AFTER the event filter ran.
    app.sendEvent(w,QEvent(event_type))
    handle=w.windowHandle()
    handle.setFlag(Qt.WindowType.WindowTitleHint,True)
    handle.setFlag(Qt.WindowType.NoTitleBarBackgroundHint,False)
    wait(app,50)
    assert not handle.flags() & Qt.WindowType.WindowTitleHint
    assert handle.flags() & Qt.WindowType.NoTitleBarBackgroundHint
    assert handle.flags() & Qt.WindowType.ExpandedClientAreaHint
    assert w.tabstrip.mapTo(w,QPoint()).y()==0
    assert not w.caption_tabs.reconcile.isActive()
    w.close()


def test_caption_native_flag_bookkeeping_across_fullscreen(app,tmp_path,monkeypatch):
    # Exercise Qt API state offscreen, without claiming Windows hit testing.
    if not hasattr(Qt.WindowType,'ExpandedClientAreaHint'):
        pytest.skip('Qt 6.8 uses the standard-caption fallback')
    from mellow import caption
    monkeypatch.setattr(caption,'supported',lambda:True)
    store=Store(tmp_path/'native-flags.db');store.set('caption_tabs',True)
    scheme=app.styleHints().colorScheme()
    w=Window(store,restore=False);w.showMaximized();wait(app)
    assert not w.windowHandle().flags() & Qt.WindowType.WindowTitleHint
    assert w.windowHandle().flags() & Qt.WindowType.ExpandedClientAreaHint
    # Re-establish the native Close control after platform normalization.
    w.windowHandle().setFlag(Qt.WindowType.WindowCloseButtonHint,False)
    w.caption_tabs.update_space()
    assert w.windowHandle().flags() & Qt.WindowType.WindowCloseButtonHint
    original_fullscreen=w.showFullScreen
    def enter_fullscreen():
        assert not w.windowHandle().flags() & Qt.WindowType.ExpandedClientAreaHint
        original_fullscreen()
    monkeypatch.setattr(w,'showFullScreen',enter_fullscreen)
    w.fullscreen();wait(app)
    assert not w.windowHandle().flags() & Qt.WindowType.ExpandedClientAreaHint
    assert w.tabstrip.layout().contentsMargins().right()==0
    w.fullscreen();wait(app)
    assert w.windowHandle().flags() & Qt.WindowType.ExpandedClientAreaHint
    assert w.tabstrip.layout().contentsMargins().right()>=144
    w.change_theme('Dark');assert app.styleHints().colorScheme()==Qt.ColorScheme.Light or app.platformName()=='offscreen'
    w.close();app.styleHints().setColorScheme(scheme)


def test_tabs_still_switch_and_close_with_optional_caption(app,pdf,tmp_path):
    store=Store(tmp_path/'tabs.db');store.set('caption_tabs',True)
    w=Window(store,restore=False);w.show();r=w.open_pdf(pdf);wait(app)
    other=tmp_path/'second.pdf';other.write_bytes(Path(pdf).read_bytes())
    w.open_pdf(other);wait(app)
    QTest.mouseClick(w.tabs,Qt.MouseButton.LeftButton,pos=w.tabs.tabRect(0).center())
    wait(app);assert w.active is r
    w.close_tab(1);assert len(w.readers)==1 and w.active is r
    w.close()


def test_signer_uses_existing_store_identity_and_stops_on_failure(tmp_path,monkeypatch):
    signer=load('sign_windows')
    files=[tmp_path/'app.exe',tmp_path/'setup.exe']
    for f in files:f.write_bytes(b'release')
    commands=[]
    monkeypatch.setattr(signer.subprocess,'run',lambda command,**kwargs:commands.append(command))
    signer.sign(files,'AB '*20,executable='signtool.exe')
    assert len(commands)==4
    assert commands[0][1:4]==['sign','/sha1','AB'*20]
    assert '/a' not in commands[0] and '/f' not in commands[0]
    assert commands[1][1:4]==['verify','/pa','/all']
    commands.clear()
    def fail(command,**kwargs):
        commands.append(command);raise CalledProcessError(1,command)
    monkeypatch.setattr(signer.subprocess,'run',fail)
    with pytest.raises(CalledProcessError):signer.sign(files,'AB'*20,executable='signtool.exe')
    assert len(commands)==1


def test_signer_rejects_invalid_inputs_before_running(tmp_path,monkeypatch):
    signer=load('sign_windows')
    file=tmp_path/'app.exe';file.write_bytes(b'release')
    monkeypatch.setattr(signer.subprocess,'run',lambda *a,**k:pytest.fail('Invalid signing request executed'))
    with pytest.raises(ValueError):signer.sign([file],'not-a-thumbprint',executable='tool')
    with pytest.raises(ValueError):signer.sign([file],'ab'*20,'http://insecure.example',executable='tool')
    with pytest.raises(ValueError):signer.sign([tmp_path/'missing.exe'],'ab'*20,executable='tool')


def test_release_policy_requires_both_trusted_signatures_and_a_real_scan():
    verifier=load('verify_windows')
    report=dict(signatures=[dict(Status='Valid',Signer='CN=Publisher')]*2,
                defender=dict(status='NoThreatsReported'))
    verifier.enforce_release_policy(report,True,True)
    for signatures in ([],[dict(Status='Valid',Signer='Publisher')],
                       [dict(Status='NotSigned')]*2,[dict(Status='HashMismatch',Signer='Publisher')]*2):
        with pytest.raises(ValueError):verifier.enforce_release_policy(dict(report,signatures=signatures),True)
    with pytest.raises(ValueError):verifier.enforce_release_policy(dict(report,defender=dict(status='NotRun')),False,True)
    verifier.enforce_release_policy(dict(signatures=[],defender=dict(status='NotRun')))


def test_notice_collection_includes_actual_source_license_and_exposes_gaps(tmp_path):
    import json
    collector=load('collect_notices')
    report=collector.collect(tmp_path/'distribution')
    root=Path(__file__).resolve().parents[1]
    assert (tmp_path/'distribution/LICENSE').read_bytes()==(root/'LICENSE').read_bytes()
    assert (tmp_path/'distribution/THIRD_PARTY.md').is_file()
    output=tmp_path/'distribution/licenses'
    assert json.loads((output/'DEPENDENCIES.json').read_text())==report
    assert not report['complete_attribution_review']
    assert any(row['name']=='pypdf' and row['notices'] for row in report['packages'])
    for row in report['packages']:
        for name in row['notices']:assert (output/name).is_file()


def test_caption_smoke_failure_releases_the_pdf_and_preserves_assertion(app,pdf,tmp_path):
    from PySide6.QtCore import QCoreApplication,QEvent
    smoke=load('caption_smoke')
    store=Store(tmp_path/'smoke.db')
    device=None
    with pytest.raises(AssertionError,match='original caption failure'):
        with smoke.smoke_window(store,lambda:wait(app,20)) as window:
            window.show();reader=window.open_pdf(pdf);wait(app)
            window.split(0,0);wait(app)
            device=reader.document().source_file
            assert device.isOpen()
            raise AssertionError('original caption failure')
    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    # On Windows, unlink would fail if any QFile still retained its handle.
    Path(pdf).unlink()
    assert not Path(pdf).exists()
