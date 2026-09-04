import importlib.util, sys
import urllib.error
from io import BytesIO
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('p2000_server', ROOT/'backend'/'server.py')
server=importlib.util.module_from_spec(spec); sys.modules[spec.name]=server; spec.loader.exec_module(server)


def test_repo_normalization():
    assert server.normalize_github_repo('owner/repo')=='owner/repo'
    assert server.normalize_github_repo('https://github.com/Owner/Repo.git')=='Owner/Repo'
    assert server.normalize_github_repo('https://evil.example/a/b')==''
    assert server.normalize_github_repo('a/b/c')==''


def test_version_compare():
    assert server._is_newer_version('v4.1.1','4.1.0')
    assert not server._is_newer_version('4.1.0','4.1.0')
    assert not server._is_newer_version('4.0.9','4.1.0')
    assert server._version_key('v4.10.0') > server._version_key('4.9.9')


def test_asset_selection_prefers_windows_zip():
    rel={'assets':[
        {'name':'Source.zip','browser_download_url':'https://github.com/o/r/releases/download/v1/Source.zip'},
        {'name':'P2000_Monitor_Windows_v4.1.1.zip','browser_download_url':'https://github.com/o/r/releases/download/v1/P2000_Monitor_Windows_v4.1.1.zip'},
    ]}
    assert server._select_github_release_asset(rel)['name'].startswith('P2000_Monitor_Windows')


def test_update_settings_auto_install_implies_check():
    x=server.sanitize_github_update_payload({'github_repo':'owner/repo','github_auto_install':True,'github_auto_check':False,'github_check_minutes':5,'github_branch_updates':True,'github_branch':'develop'})
    assert x['github_auto_install'] is True
    assert x['github_auto_check'] is True
    assert x['github_check_minutes']==5
    assert x['github_branch_updates'] is True
    assert x['github_branch']=='develop'


def test_update_interval_never_hammers_public_github_api():
    x=server.sanitize_github_update_payload({'github_repo':'owner/repo','github_check_minutes':1})
    assert x['github_check_minutes']==5


def test_legacy_hourly_interval_migrates_to_five_minutes():
    x=server.github_update_config({'github_repo':'owner/repo','github_check_hours':6})
    assert x['github_check_minutes']==5
    assert 'github_check_hours' not in x


def test_central_settings_config_is_sanitized():
    x=server.sanitize_github_settings_sync_payload({'github_repo':'owner/repo','github_settings_auto_sync':True,'github_settings_path':'config/monitor.json','github_settings_branch':'main','github_settings_minutes':1})
    assert x['github_settings_auto_sync'] is True
    assert x['github_settings_path']=='config/monitor.json'
    assert x['github_settings_branch']=='main'
    assert x['github_settings_minutes']==1


def test_branch_update_metadata_uses_codeload():
    original,original_head=server._github_raw_file,server._github_branch_head
    requested=[]
    server._github_raw_file=lambda repo,path,branch:(requested.append(branch) or b'4.2.1\n')
    server._github_branch_head=lambda repo,branch:'a'*40
    try: x=server._github_latest_branch('owner/repo','main')
    finally: server._github_raw_file,server._github_branch_head=original,original_head
    assert x['version']=='4.2.1'
    assert x['source_kind']=='branch'
    assert x['revision']=='a'*40
    assert requested==['a'*40]
    assert x['asset']['url'].startswith('https://codeload.github.com/owner/repo/')
    assert x['asset']['url'].endswith('a'*40)


def test_same_version_new_commit_is_an_update_once():
    candidate={'repo':'owner/repo','version':'4.2.5','tag':'main','source_kind':'branch','revision':'b'*40}
    available,reason=server._github_update_available(candidate,'4.2.5',{})
    assert available and reason=='revision'
    available,reason=server._github_update_available(candidate,'4.2.5',{'repo':'owner/repo','branch':'main','revision':'b'*40})
    assert not available and reason==''


def test_equal_version_prefers_branch_commit_over_release():
    old_release,old_branch=server._github_latest_release,server._github_latest_branch
    base={'repo':'owner/repo','version':'4.2.5','tag':'v4.2.5','asset':{'name':'release.zip','url':'https://github.com/a','size':1}}
    server._github_latest_release=lambda repo:dict(base)
    server._github_latest_branch=lambda repo,branch:{**base,'tag':branch,'source_kind':'branch','revision':'c'*40}
    try: selected=server._github_latest_software('owner/repo','main',True)
    finally: server._github_latest_release,server._github_latest_branch=old_release,old_branch
    assert selected['source_kind']=='branch'
    assert selected['revision']=='c'*40


def test_api_403_uses_public_branch_fallback():
    old_release,old_branch,old_public=server._github_latest_release,server._github_latest_branch,server._github_latest_branch_public
    forbidden=lambda *args,**kwargs: (_ for _ in ()).throw(urllib.error.HTTPError('https://api.github.com',403,'forbidden',{},BytesIO()))
    server._github_latest_release=forbidden
    server._github_latest_branch=forbidden
    server._github_latest_branch_public=lambda repo,branch,reason:{'repo':repo,'version':'4.4.14','tag':branch,'source_kind':'branch','revision':'d'*40,'public_fallback':True,'fallback_reason':reason,'asset':{'name':'fallback.zip','url':'https://codeload.github.com/owner/repo/zip/'+'d'*40,'size':0}}
    try: selected=server._github_latest_software('owner/repo','main',True)
    finally: server._github_latest_release,server._github_latest_branch,server._github_latest_branch_public=old_release,old_branch,old_public
    assert selected['public_fallback'] is True
    assert '403' in selected['fallback_reason']


def test_public_fallback_without_sha_never_reinstalls_equal_version():
    candidate={'repo':'owner/repo','version':'4.4.13','tag':'main','source_kind':'branch','revision':'','public_fallback':True}
    assert server._github_update_available(candidate,'4.4.13',{}) == (False,'')


def test_public_fallback_without_sha_still_offers_higher_version():
    candidate={'repo':'owner/repo','version':'4.4.14','tag':'main','source_kind':'branch','revision':'','public_fallback':True}
    assert server._github_update_available(candidate,'4.4.13',{}) == (True,'version')

if __name__=='__main__':
    for name,fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn): fn(); print(name,'OK')
