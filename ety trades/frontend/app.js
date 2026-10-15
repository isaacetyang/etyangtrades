const $ = id => document.getElementById(id);
let sessionId = null, socket = null, serverConfig = {};
function log(message, cls="") {
  const row=document.createElement("div"); row.className="log "+cls;
  row.textContent=`[${new Date().toLocaleTimeString()}] ${message}`;
  $("logs").prepend(row);
}
async function getConfig(){
  try{
    const response=await fetch("/api/config");
    if(!response.ok) throw Error(`Config endpoint returned HTTP ${response.status}`);
    serverConfig=await response.json();
    $("serverMode").textContent=serverConfig.app_id_configured
      ? (serverConfig.live_trading_enabled?"LIVE GATE ENABLED":"PAPER READY")
      : "DERIV APP ID MISSING";
    if(!serverConfig.live_trading_enabled){$("executionMode").querySelector('option[value="real_auto"]').disabled=true;}
    if(!serverConfig.app_id_configured){
      $("connectBtn").disabled=true;
      log(serverConfig.message || "Set DERIV_APP_ID in Render Environment Variables and redeploy.","bad");
    }
  }catch(e){log("Could not read server config: "+e.message,"bad");}
}
async function analyse(){
  $("analyseBtn").disabled=true;
  try{
    const r=await fetch("/api/analyse",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({symbol:$("symbol").value,token:$("analysisToken").value})});
    const d=await r.json(); if(!r.ok)throw Error(d.detail||"Analysis failed");
    const a=d.analysis;
    $("signal").textContent=a.signal; $("signal").style.color=a.signal==="CALL"?"var(--green)":a.signal==="PUT"?"var(--red)":"var(--amber)";
    $("confidence").textContent=a.confidence+"%"; $("latestPrice").textContent=d.latest_price??"—";
    $("ema9").textContent=a.ema9??"—"; $("ema21").textContent=a.ema21??"—";
    $("rsi").textContent=a.rsi14??"—"; $("momentum").textContent=(a.momentum_pct??0)+"%";
    $("analysisReason").textContent=a.reason+" Data points: "+d.points;
    const freq=d.digits.frequencies||{};
    $("digitStats").innerHTML=Object.keys(freq).length?Object.entries(freq).map(([k,v])=>`<div class="digit">${k}<b>${v}</b><small>hits</small></div>`).join(""):"Digit stats unavailable";
    log(`Analysis ${d.symbol}: ${a.signal} (${a.confidence}% confidence)`,a.signal==="WAIT"?"warn":"good");
  }catch(e){log(e.message,"bad");}finally{$("analyseBtn").disabled=false;}
}
async function connect(){
  if(!serverConfig.app_id_configured){
    log("Deriv App ID is not configured on the server. Add DERIV_APP_ID in Render and redeploy.","bad");
    return;
  }
  $("connectBtn").disabled=true;
  try{
    const r=await fetch("/api/connect",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({token:$("token").value,account_mode:$("accountMode").value})});
    const d=await r.json(); if(!r.ok)throw Error(d.detail||"Connection failed");
    sessionId=d.session_id; $("accountId").textContent=d.loginid||"Connected";
    $("balance").textContent=`${d.balance} ${d.currency}`; $("modeLabel").textContent=d.is_virtual?"DEMO":"REAL";
    log(`Connected ${d.loginid} (${d.is_virtual?"virtual":"real"})`,"good");
  }catch(e){log(e.message,"bad");}finally{$("connectBtn").disabled=false;}
}
function start(){
  const mode=$("executionMode").value;
  if(mode!=="paper"&&!sessionId){log("Connect the matching Deriv account before auto trading.","bad");return;}
  if(mode==="real_auto"&&!$("realConfirm").checked){log("Explicit real-trading confirmation is required.","bad");return;}
  if(socket&&socket.readyState===WebSocket.OPEN){log("Bot is already running.","warn");return;}
  socket=new WebSocket(`${location.protocol==="https:"?"wss":"ws"}://${location.host}/ws/bot`);
  socket.onopen=()=>{
    socket.send(JSON.stringify({action:"start",session_id:sessionId,mode,
      confirm_real:$("realConfirm").checked,symbol:$("symbol").value,
      contract_type:$("contractType").value,stake:Number($("stake").value),
      min_confidence:Number($("minConfidence").value),paper_balance:10}));
    $("startBtn").disabled=true;$("stopBtn").disabled=false;
    log("Bot start command sent.","good");
  };
  socket.onmessage=e=>{
    const d=JSON.parse(e.data);
    if(d.type==="analysis"){const a=d.analysis;$("signal").textContent=a.signal;$("confidence").textContent=a.confidence+"%";$("latestPrice").textContent=d.latest_price??"—";$("analysisReason").textContent=a.reason;}
    else if(d.type==="paper_trade")log(`PAPER ${d.contract_type} ${d.symbol} stake ${d.stake}; confidence ${d.confidence}%`,"good");
    else if(d.type==="trade_open")log(`ORDER OPEN #${d.contract_id}: ${d.contract_type} ${d.symbol}, stake ${d.stake}`,"warn");
    else if(d.type==="trade_closed")log(`ORDER CLOSED #${d.contract_id}: P/L ${d.profit}; balance estimate ${d.balance_estimate}` ,d.profit>=0?"good":"bad");
    else if(d.type==="risk_stop")log("RISK STOP: "+d.message,"bad");
    else if(d.type==="recovery")log(`Recovery check ${d.attempts_used}/${d.max_attempts}: ${d.message}`,"warn");
    else log(d.message||JSON.stringify(d),d.type==="error"?"bad":"");
  };
  socket.onclose=()=>{ $("startBtn").disabled=false;$("stopBtn").disabled=true;};
  socket.onerror=()=>log("Bot WebSocket connection error.","bad");
}
function stop(){
  if(socket&&socket.readyState===WebSocket.OPEN)socket.send(JSON.stringify({action:"stop"}));
  if(socket)socket.close();$("startBtn").disabled=false;$("stopBtn").disabled=true;log("Stop requested.","warn");
}
$("analyseBtn").onclick=analyse;$("connectBtn").onclick=connect;$("startBtn").onclick=start;$("stopBtn").onclick=stop;
$("clearLog").onclick=()=>$("logs").innerHTML="";
$("executionMode").onchange=()=>{$("modeLabel").textContent=$("executionMode").value.replace("_"," ").toUpperCase();};
getConfig();
