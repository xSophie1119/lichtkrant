/* One pairing session for the dashboard, full settings, wizard and monitor. */
(() => {
  'use strict';
  async function request(path, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(path, {cache: 'no-store', credentials: 'same-origin', ...options, signal: controller.signal});
      const data = await response.json();
      if (!response.ok || data.ok === false) {
        const error = new Error(data.error || `HTTP ${response.status}`);
        error.status = response.status;
        throw error;
      }
      return data;
    } finally { clearTimeout(timer); }
  }
  async function login(token) {
    return request('/api/remote/session', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-P2000-Admin-Token': token.trim()}, body: '{}'});
  }
  function showLogin(message) {
    return new Promise(resolve => {
      const dialog = document.createElement('dialog');
      dialog.style.cssText = 'box-sizing:border-box;width:min(430px,calc(100% - 32px));border:1px solid #355561;border-radius:22px;padding:28px;background:#101d28;color:#f2f8fa;font:16px system-ui';
      dialog.innerHTML = '<form><h2 style="margin-top:0">Koppel je telefoon</h2><p>Open op de lichtkrant-pc het bedienpaneel en scan de QR-code. Of plak hieronder de koppelcode.</p><label for="pair-token">Koppelcode</label><input id="pair-token" type="password" autocomplete="off" required style="box-sizing:border-box;width:100%;font:16px system-ui;padding:14px;margin:12px 0;border-radius:10px"><p role="status" style="color:#ffb6a6"></p><button style="width:100%;padding:14px;border:0;border-radius:10px;background:#65e7c0;color:#09231e;font:600 16px system-ui">Verbinden</button></form>';
      document.body.append(dialog);
      dialog.querySelector('[role=status]').textContent = message || '';
      dialog.addEventListener('cancel', event => event.preventDefault());
      dialog.showModal();
      dialog.querySelector('form').onsubmit = async event => {
        event.preventDefault();
        const button = dialog.querySelector('button'); button.disabled = true;
        try { const session=await login(dialog.querySelector('input').value); dialog.close(); dialog.remove(); resolve(session); }
        catch (error) { dialog.querySelector('[role=status]').textContent = error.status === 401 ? 'Deze koppelcode klopt niet. Scan de QR-code opnieuw.' : error.message; }
        finally { button.disabled = false; }
      };
    });
  }
  async function ready() {
    if (document.readyState === 'loading') await new Promise(resolve => document.addEventListener('DOMContentLoaded', resolve, {once: true}));
    const token = new URLSearchParams(location.hash.slice(1)).get('token');
    if (token) {
      // The fragment never reaches the HTTP server; remove it from browser history.
      history.replaceState(null, '', location.pathname + location.search);
      try { await login(token); } catch (error) { return showLogin(error.message); }
    }
    try { return await request('/api/remote/session'); }
    catch (error) { return showLogin(error.status === 401 ? '' : 'Geen verbinding met de lichtkrant. Controleer wifi en de pc.'); }
  }
  window.P2000Auth = {request, login, ready: ready()};
})();
