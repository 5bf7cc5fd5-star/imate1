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
    var people=nav.querySelector(".sec");
    var after=document.querySelector('[data-page="credit"]');
    if(after && after.parentNode) after.parentNode.insertBefore(btn, after.nextSibling);
    else nav.appendChild(btn);
    var main=document.querySelector("main.page");
    if(!main) return;
    var sec=document.createElement("section");
    sec.id="page-staff";
    sec.className="hidden";
    sec.innerHTML='<div class="card"><h3>Staff & positions</h3><p class="empty" style="padding:0 0 12px">Assign the live roles: Owner, Full Admin (deposits & withdrawals), Support (password help only), Finance, Inventory, Viewer.</p><div id="staffTable"></div></div><div class="card"><h3>Add staff</h3><div class="grid2"><div class="field"><label>Name</label><input id="stName"></div><div class="field"><label>Email</label><input id="stEmail"></div><div class="field"><label>Phone</label><input id="stPhone"></div><div class="field"><label>Password</label><input id="stPass" type="password"></div><div class="field"><label>Position</label><select id="stPos"></select></div></div><button class="chip chip-p" onclick="createStaff()">Create staff</button></div>';
    main.appendChild(sec);
    if(window.PAGES && window.PAGES.indexOf("staff")<0) window.PAGES.push("staff");
    return true;
  }
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
      var h="<table><thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Position</th><th>Withdraw</th><th>Deposit</th><th>Password</th><th></th></tr></thead><tbody>";
      users.forEach(function(u){
        if(!(u.is_admin||u.is_support||u.position||(u.email||"").toLowerCase().indexOf("kato")>=0||(u.email||"")==="k_hmed@yahoo.com")) {
          /* still list everyone so you can promote */
        }
        var pos=u.position||(u.is_admin?"full_admin":(u.is_support?"support":"viewer"));
        h+="<tr><td>"+(u.name||"—")+"</td><td>"+(u.email||"")+"</td><td>"+(u.phone||"")+"</td><td><select onchange=\"assignPos('"+(u.id||"")+"',this.value)\">";
        positions.forEach(function(p){ h+="<option value='"+p.id+"'"+(p.id===pos?" selected":"")+">"+p.label+"</option>"; });
        h+="</select></td><td>"+(u.can_approve_withdraw?"Yes":"No")+"</td><td>"+(u.can_approve_deposit?"Yes":"No")+"</td><td>"+(u.can_approve_password?"Yes":"No")+"</td><td></td></tr>";
      });
      box.innerHTML=h+"</tbody></table>";
    }).catch(function(e){
      var box=document.getElementById("staffTable");
      if(box) box.innerHTML="<div class='empty'>"+(e.message||e)+"</div>";
    });
  };
  window.assignPos=function(id, position){
    api("/api/admin/staff/set","POST",{id:id, position:position}).then(function(){ toast("Position saved"); loadStaff(); refreshAll(); }).catch(function(e){ toast(e.message); });
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
