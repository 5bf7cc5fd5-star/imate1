(function(){
  if(!/\/admin/.test(location.pathname) && document.title.indexOf("Console")<0) return;
  function ready(){
    var nav=document.querySelector(".side-nav");
    if(!nav || document.getElementById("page-staff")) return true;
    var btn=document.createElement("button");
    btn.setAttribute("data-page","staff");
    btn.textContent="Staff & positions";
    btn.onclick=function(){
      if(typeof goPage==="function") goPage("staff", btn);
      loadStaff();
    };
    var after=document.querySelector('[data-page="credit"]');
    if(after && after.parentNode) after.parentNode.insertBefore(btn, after.nextSibling);
    else nav.appendChild(btn);
    var main=document.querySelector("main.page");
    if(!main) return;
    var sec=document.createElement("section");
    sec.id="page-staff";
    sec.className="hidden";
    sec.innerHTML='<div class="card"><h3>Staff & positions</h3><p class="empty" style="padding:0 0 12px">Click a staff row to credit their wallet. Assign Owner / Full Admin / Support / Finance / Inventory / Viewer.</p><div id="staffTable"></div></div><div class="card hidden" id="staffCreditCard"><h3 id="staffCreditTitle">Credit wallet</h3><div class="grid2"><div class="field"><label>Staff</label><input id="scWho" readonly></div><div class="field"><label>Current balance</label><input id="scBal" readonly></div><div class="field"><label>Amount (+ credit / − deduct)</label><input id="scAmt" type="number" step="0.01"></div><div class="field"><label>Note</label><input id="scNote" placeholder="Staff wallet credit"></div></div><button class="chip chip-p" onclick="creditStaff()">Credit this wallet</button></div><div class="card"><h3>Add staff</h3><div class="grid2"><div class="field"><label>Name</label><input id="stName"></div><div class="field"><label>Email</label><input id="stEmail"></div><div class="field"><label>Phone</label><input id="stPhone"></div><div class="field"><label>Password</label><input id="stPass" type="password"></div><div class="field"><label>Position</label><select id="stPos"></select></div></div><button class="chip chip-p" onclick="createStaff()">Create staff</button></div>';
    main.appendChild(sec);
    if(window.PAGES && window.PAGES.indexOf("staff")<0) window.PAGES.push("staff");
    return true;
  }
  var PICK=null;
  window.loadStaff=function(){
    Promise.all([
      api("/api/admin/staff").catch(function(){return api("/api/admin/users");}),
      api("/api/admin/positions").catch(function(){return {positions:[]};})
    ]).then(function(res){
      var users=(res[0].staff||res[0].users||[]);
      var positions=res[1].positions||[
        {id:"owner",label:"Owner"},
        {id:"full_admin",label:"Full Admin — Deposits & Withdrawals"},
        {id:"support",label:"Support — Password help only"},
        {id:"finance",label:"Finance — Pool & credits"},
        {id:"inventory",label:"Inventory — Company pool reports"},
        {id:"viewer",label:"Viewer"}
      ];
      var sel=document.getElementById("stPos");
      if(sel && !sel.options.length){
        positions.forEach(function(p){ var o=document.createElement("option"); o.value=p.id; o.textContent=p.label; sel.appendChild(o); });
        sel.value="support";
      }
      var box=document.getElementById("staffTable");
      if(!box) return;
      var h="<table><thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>ID</th><th>Position</th><th>Wallet</th><th>Credit</th></tr></thead><tbody>";
      users.forEach(function(u,i){
        var pos=u.position||(u.is_admin?"full_admin":(u.is_support?"support":"viewer"));
        h+="<tr style='cursor:pointer' onclick='pickStaff('+i+')'>";
        h+="<td>"+(u.name||"—")+"</td><td>"+(u.email||"")+"</td><td>"+(u.phone||"")+"</td><td class='mono'>"+(u.member_no||u.id||"")+"</td><td><select onclick='event.stopPropagation()' onchange=\"assignPos('"+(u.id||"")+"',this.value)\">";
        positions.forEach(function(p){ h+="<option value='"+p.id+"'"+(p.id===pos?" selected":"")+">"+p.label+"</option>"; });
        h+="</select></td><td><b>$"+Number(u.balance||0).toLocaleString(undefined,{minimumFractionDigits:2})+"</b></td>";
        h+="<td><button class='chip chip-p' onclick='event.stopPropagation();pickStaff("+i+")'>Credit</button></td></tr>";
      });
      box.innerHTML=h+"</tbody></table>";
      window.__staffRows=users;
    }).catch(function(e){
      var box=document.getElementById("staffTable");
      if(box) box.innerHTML="<div class='empty'>"+(e.message||e)+"</div>";
    });
  };
  window.pickStaff=function(i){
    var u=(window.__staffRows||[])[i];
    if(!u) return;
    PICK=u;
    var card=document.getElementById("staffCreditCard");
    card.classList.remove("hidden");
    document.getElementById("staffCreditTitle").textContent="Credit wallet — "+(u.name||u.email);
    document.getElementById("scWho").value=(u.name||"")+" · "+(u.email||u.phone||"")+" · "+(u.member_no||u.id||"");
    document.getElementById("scBal").value=Number(u.balance||0).toFixed(2);
    document.getElementById("scAmt").value="";
    document.getElementById("scAmt").focus();
    card.scrollIntoView({behavior:"smooth",block:"nearest"});
  };
  window.creditStaff=function(){
    if(!PICK){ toast("Click a staff first"); return; }
    var amt=Number(document.getElementById("scAmt").value);
    if(!amt){ toast("Enter amount"); return; }
    api("/api/admin/credit","POST",{
      identifier: PICK.email||PICK.phone||PICK.id,
      amount: amt,
      note: document.getElementById("scNote").value||("Staff credit — "+(PICK.name||""))
    }).then(function(){
      toast("Credited "+(PICK.name||PICK.email));
      document.getElementById("scAmt").value="";
      loadStaff();
      if(typeof refreshAll==="function") refreshAll();
    }).catch(function(e){ toast(e.message); });
  };
  window.assignPos=function(id, position){
    api("/api/admin/staff/set","POST",{id:id, position:position}).then(function(){ toast("Position saved"); loadStaff(); }).catch(function(e){ toast(e.message); });
  };
  window.createStaff=function(){
    api("/api/admin/staff/create","POST",{
      name:document.getElementById("stName").value,
      email:document.getElementById("stEmail").value,
      phone:document.getElementById("stPhone").value,
      password:document.getElementById("stPass").value,
      position:document.getElementById("stPos").value
    }).then(function(){ toast("Staff created"); loadStaff(); }).catch(function(e){ toast(e.message); });
  };
  function boot(){ if(!ready()) setTimeout(boot, 300); }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
