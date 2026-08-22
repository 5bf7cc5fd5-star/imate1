(function(){
  function noOf(u){
    if(!u) return "";
    return u.member_no || u.memberNo || u.member_id || "";
  }
  function paint(){
    var u=null;
    try{ if(typeof currentUser==="function") u=currentUser(); }catch(e){}
    if(!u){
      try{
        var raw=localStorage.getItem("oc_user")||localStorage.getItem("user")||sessionStorage.getItem("oc_user");
        if(raw) u=JSON.parse(raw);
      }catch(e){}
    }
    var no=noOf(u);
    if(!no) return;
    var nameEl=document.getElementById("myNameDisplay");
    if(nameEl){
      var base=(u.name||nameEl.textContent||"User").replace(/\s*OCS-[A-Z0-9]+/g,"").trim();
      nameEl.innerHTML=base+' <span id="myMemberNo" style="color:#2ee56a;font-weight:800;margin-left:6px;letter-spacing:.4px">'+no+'</span>';
    }
    var bar=document.querySelector(".wallet-bar .side span");
    if(bar && bar.textContent.indexOf("OCS-")<0){
      bar.textContent="Wallet · "+no;
    }
    var phone=document.getElementById("myPhoneDisplay");
    if(phone && phone.parentElement && !document.getElementById("myMemberNoLine")){
      var s=document.createElement("div");
      s.id="myMemberNoLine";
      s.style.cssText="font-size:12px;color:#9aa3ad;margin-top:2px";
      s.textContent="ID "+no;
    }
  }
  function hookMe(){
    if(window.__ocMeHook) return;
    window.__ocMeHook=true;
    var orig=window.fetch;
    if(!orig) return;
    window.fetch=function(){
      return orig.apply(this, arguments).then(function(res){
        try{
          var url=String(arguments[0]||"");
          if(url.indexOf("/api/me")>=0 || url.indexOf("/api/login")>=0 || url.indexOf("/api/register")>=0){
            res.clone().json().then(function(j){
              var u=j.user||j;
              if(u && u.member_no){
                try{ localStorage.setItem("oc_user", JSON.stringify(u)); }catch(e){}
                setTimeout(paint, 50);
              }
            }).catch(function(){});
          }
        }catch(e){}
        return res;
      });
    };
  }
  hookMe();
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", paint);
  else paint();
  setTimeout(paint, 400);
  setTimeout(paint, 1200);
  setTimeout(paint, 2500);
  document.addEventListener("click", function(){ setTimeout(paint, 80); }, true);
})();
