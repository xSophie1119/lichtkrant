/* Screen-only transport: real canvas previews and per-command receipts. */
(() => {
  'use strict';
  let uploading = false, lastUpload = 0;
  window.P2000ScreenRemote = {
    async receipt(request, clientId, seq, status, detail) {
      if (!seq) return;
      try { await request('/api/remote/receipt', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({client_id:clientId,seq,status,detail})}); } catch {}
    },
    async preview(request, clientId, canvas, snapshot) {
      if(uploading || Date.now()-lastUpload<4000) return;
      uploading=true;lastUpload=Date.now();
      try {
        const small=document.createElement('canvas');
        small.width=480;small.height=Math.max(1,Math.round(480*canvas.height/canvas.width));
        if(small.height>480){small.width=Math.round(480*canvas.width/canvas.height);small.height=480;}
        small.getContext('2d').drawImage(canvas,0,0,small.width,small.height);
        let image=small.toDataURL('image/jpeg',.62);
        if(image.length>58000)image=small.toDataURL('image/jpeg',.3);
        if(image.length>58000)return;
        await request('/api/remote/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({client_id:clientId,image,...snapshot})});
      } catch { /* Cross-origin photos may taint canvas; heartbeat still works. */ }
      finally {uploading=false;}
    }
  };
})();
