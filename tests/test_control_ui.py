from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT / "frontend" / "control.html").read_text(encoding="utf-8")
css = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")
js = (ROOT / "frontend" / "control.js").read_text(encoding="utf-8")
index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def test_settings_page_contract():
    for element_id in (
        "saveBtn", "pageFeedback", "githubSettingsCard", "githubSettingsAutoSyncInput",
        "saveGithubSettingsBtn", "pullGithubSettingsBtn", "githubBranchUpdatesInput",
        "vehicleOverridesCard", "vehicleOverrideCallsign", "saveVehicleOverrideBtn", "vehicleOverrideList",
    ):
        assert f'id="{element_id}"' in html
    for class_name in (".control-card", ".header-actions", ".two-col", ".three-col", ".status-grid", ".page-feedback"):
        assert class_name in css
    for function_name in ("saveGithubSettingsSync", "pullGithubSettings", "githubSettingsStatus", "saveVehicleOverride", "loadVehicleOverrides", "waitForTestResult"):
        assert f"function {function_name}" in js
    assert "force_audio:true" in js
    assert "/api/test-status?token=" in js


def test_lightkrant_settings_button_has_direct_fallback():
    assert 'id="settingsBtn"' in index
    assert 'href="/control.html"' in index
    assert "location.assign('/control.html')" in (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")


if __name__ == "__main__":
    test_settings_page_contract()
    test_lightkrant_settings_button_has_direct_fallback()
    print("control UI tests OK")
