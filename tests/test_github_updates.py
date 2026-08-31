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
    x=server.sanitize_github_update_payload({'github_repo':'owner/repo','github_auto_install':True,'github_auto_check':False,'github_check_hours':3})
    assert x['github_auto_install'] is True
    assert x['github_auto_check'] is True
    assert x['github_check_hours']==3

if __name__=='__main__':
    for name,fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn): fn(); print(name,'OK')
