(function(){
  function money(n){n=Number(n||0);return (n<0?"-":"")+"$"+Math.abs(n).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});}
  function paint(){
    var u=null;
    try{ if(typeof currentUser==="function") u=currentUser(); }catch(e){}
    if(!u){
      try{ var raw=localStorage.getItem("oc_user"); if(raw) u=JSON.parse(raw); }catch(e){}
    }
    if(!u) return;
    var host=document.getElementById("txList")||document.getElementById("incomeTx")||document.querySelector("#my .card, #income");
    var box=document.getElementById("ocTxHistory");
    if(!box){
      box=document.createElement("div");
      box.id="ocTxHistory";
      box.style.cssText="margin:14px 0 72px;padding:0 4px;color:#fff";
      var page=document.getElementById("my")||document.getElementById("income");
      if(page) page.appendChild(box);
      else return;
    }
    var txs=(u.transactions||[]).slice(0,80);
    var html='<div style="display:flex;justify-content:space-between;align-items:baseline;margin:8px 0"><h3 style="margin:0;font-size:16px">Transaction history</h3><span style="color:#8b93a0;font-size:11px">'+txs.length+' rows</span></div>';
    if(!txs.length){ box.innerHTML=html+'<div style="color:#8b93a0;font-size:13px">No movements yet</div>'; return; }
    html+='<div style="border-top:1px solid #163326">';
    txs.forEach(function(t){
      var amt=Number(t.amount||0);
      html+='<div style="display:flex;justify-content:space-between;gap:10px;padding:10px 0;border-bottom:1px solid #163326">'+
        '<div><div style="font-weight:700">'+(t.type||"Movement")+'</div><div style="color:#8b93a0;font-size:11px">'+(t.date||t.at||"")+'</div></div>'+
        '<div style="font-weight:800;color:'+(amt<0?"#ff5b5b":"#2ee56a")+'">'+money(amt)+'</div></div>';
    });
    html+='</div>';
    box.innerHTML=html;
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", paint);
  else paint();
  setTimeout(paint, 500);
  setTimeout(paint, 1600);
  document.addEventListener("click", function(){ setTimeout(paint, 120); }, true);
})();
