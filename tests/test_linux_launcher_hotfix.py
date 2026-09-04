from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
start=(ROOT/'START_P2000.sh').read_text(encoding='utf-8')
installer=(ROOT/'INSTALL_P2000.sh').read_text(encoding='utf-8')
check=(ROOT/'LINUX_CHECK.sh').read_text(encoding='utf-8')
desktop=(ROOT/'tools'/'linux_desktop.py').read_text(encoding='utf-8')
supervisor=(ROOT/'tools'/'supervisor.py').read_text(encoding='utf-8')
version=(ROOT/'VERSION').read_text().strip()
checks={
    'version_443': version=='4.4.3',
    'shared_desktop_helper': 'tools/linux_desktop.py' in start and (ROOT/'tools'/'linux_desktop.py').is_file(),
    'snap_safe_profile': 'HOME / "snap" / c.snap_package / "common"' in desktop,
    'flatpak_support': 'FLATPAKS' in desktop and 'flatpak' in desktop and '.var' in desktop,
    'browser_probe': 'probe_seconds' in desktop and 'matching_pids' in desktop and '/proc' in desktop,
    'multi_browser_fallback': 'for c in candidates' in desktop,
    'wayland_x11_fallback': 'return ["x11", "wayland", "auto"]' in desktop,
    'visible_error_path': 'pause_on_error' in start and 'notify_error' in start,
    'wizard_shared_browser': 'LINUX_OPEN_PAGE.sh' in (ROOT/'CONFIGURATIE_WIZARD.sh').read_text(),
    'wizard_watchdog_grace': 'setup-required' in supervisor and 'Configuratiewizard afgerond' in supervisor,
    'debug_launcher': (ROOT/'START_P2000_DEBUG.sh').exists(),
    'linux_check_logs': 'for f in startup backend browser supervisor autostart' in check,
    'desktop_shortcuts': 'p2000-monitor-wizard.desktop' in installer and 'p2000-monitor-debug.desktop' in installer,
}
failed=[k for k,v in checks.items() if not v]
print(f"Linux launcher v4.4.3 checks: {len(checks)-len(failed)}/{len(checks)}")
if failed:
    print('FAILED:', ', '.join(failed))
    raise SystemExit(1)
