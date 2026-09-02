import importlib.util, sys
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
    original=server._github_file
    server._github_file=lambda repo,path,branch:{'body':b'4.2.1\n','sha':'abc'}
    try: x=server._github_latest_branch('owner/repo','main')
    finally: server._github_file=original
    assert x['version']=='4.2.1'
    assert x['source_kind']=='branch'
    assert x['asset']['url'].startswith('https://codeload.github.com/owner/repo/')

if __name__=='__main__':
    for name,fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn): fn(); print(name,'OK')
