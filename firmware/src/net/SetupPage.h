#pragma once
#include <Arduino.h>

// Served at "/". Lets any phone pick a Wi-Fi network without the app.
static const char SETUP_PAGE[] PROGMEM = R"HTML(<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dot Matrix setup</title>
<style>
:root{--bg:#0b0f0c;--card:#131a15;--line:#223026;--fg:#e6efe8;--dim:#8aa392;--acc:#3ddc84}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;padding:20px 16px}
main{max-width:440px;margin:0 auto}
h1{font-size:22px;margin:4px 0 2px;letter-spacing:.5px}
.sub{color:var(--dim);margin:0 0 18px;font-size:14px}
.dots{display:flex;gap:3px;margin-bottom:14px}.dots i{width:6px;height:6px;border-radius:50%;background:var(--acc);opacity:.25}
.dots i:nth-child(3n){opacity:1}.dots i:nth-child(5n){opacity:.6}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin-bottom:14px}
.row{display:flex;justify-content:space-between;padding:3px 0;font-size:14px}.row span:first-child{color:var(--dim)}
label{display:block;font-size:13px;color:var(--dim);margin:10px 0 6px}
input,select{width:100%;padding:12px;border-radius:10px;border:1px solid var(--line);background:#0e1410;color:var(--fg);font-size:16px}
button{width:100%;margin-top:16px;padding:13px;border:0;border-radius:10px;background:var(--acc);color:#04210f;font-weight:600;font-size:16px}
button:disabled{opacity:.5}.msg{margin-top:12px;font-size:14px;color:var(--dim)}
.link{color:var(--acc)}
</style></head><body><main>
<div class="dots"><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div>
<h1>Dot Matrix</h1><p class="sub">Connect the display to your Wi-Fi</p>

<div class="card" id="status"><div class="row"><span>Status</span><span>…</span></div></div>

<form class="card" id="f">
<label for="ssid">Network</label>
<select id="ssid" name="ssid"><option>Scanning…</option></select>
<label for="other">…or type the name</label>
<input id="other" placeholder="Network name" autocomplete="off">
<label for="pw">Password</label>
<input id="pw" name="password" type="password" autocomplete="off">
<button id="b" type="submit">Save and connect</button>
<div class="msg" id="m"></div>
</form>
</main>
<script>
const $=id=>document.getElementById(id);
async function status(){try{const s=await (await fetch('/api/status')).json();
 const rows=Object.entries({'Device':s.name,'Firmware':s.fw,'Wi-Fi':s.wifi,'Address':s.ip}).filter(([k,v])=>v);
 $('status').innerHTML=rows.map(([k,v])=>`<div class="row"><span>${k}</span><span>${v}</span></div>`).join('');}catch(e){}}
async function scan(){try{const r=await fetch('/api/scan');const j=await r.json();
 if(j.scanning){setTimeout(scan,1500);return}
 const sel=$('ssid');sel.innerHTML='';
 j.networks.sort((a,b)=>b.rssi-a.rssi).forEach(n=>{const o=document.createElement('option');
  o.value=n.ssid;o.textContent=n.ssid+(n.open?'':' 🔒');sel.appendChild(o)});
 if(!j.networks.length)sel.innerHTML='<option value="">No networks found</option>';
}catch(e){setTimeout(scan,3000)}}
$('f').onsubmit=async e=>{e.preventDefault();
 const ssid=$('other').value.trim()||$('ssid').value;if(!ssid){$('m').textContent='Pick a network';return}
 $('b').disabled=true;$('m').textContent='Saving…';
 const body=new URLSearchParams({ssid,password:$('pw').value});
 try{const r=await fetch('/api/wifi',{method:'POST',body});if(!r.ok)throw 0;
  $('m').innerHTML='Saved. The display restarts and joins <b>'+ssid+'</b>. Put your phone back on that network, then open the app (or <span class="link">http://dotmatrix.local</span>).';
 }catch(e){$('m').textContent='Could not save, try again.';$('b').disabled=false}};
status();scan();
</script></body></html>)HTML";
