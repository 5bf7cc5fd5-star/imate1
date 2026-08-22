(function(){
  function $(id){ return document.getElementById(id); }
  function restyle(){
    var s=$("authScreen")||document.querySelector(".auth-screen");
    if(!s) return;
    document.documentElement.classList.add("auth-open");
    document.body.classList.add("auth-open");
    ["auth-logo","wy-logo","wy-brand","auth-bg","auth-hero"].forEach(function(cls){
      s.querySelectorAll("."+cls).forEach(function(el){ el.style.setProperty("display","none","important"); });
    });
    var pack=$("ocPack");
    if(pack){
      while(pack.firstChild) s.insertBefore(pack.firstChild, pack);
      pack.remove();
    }
    if(!$("fbBack")){
      var b=document.createElement("button");
      b.id="fbBack"; b.type="button"; b.textContent="\u2039";
      b.onclick=function(){
        if(typeof switchAuth==="function") switchAuth("login");
        else if(history.length>1) history.back();
      };
      s.prepend(b);
    }
    if(!$("fbMarkWrap")){
      var w=document.createElement("div");
      w.id="fbMarkWrap";
      var img=document.createElement("img");
      img.src="/own-club-logo.jpg";
      img.alt="Own Club";
      w.appendChild(img);
      var back=$("fbBack");
      if(back && back.nextSibling) s.insertBefore(w, back.nextSibling);
      else s.insertBefore(w, s.firstChild);
    }
    var mark=$("fbMarkWrap");
    var form=$("loginForm")||s.querySelector(".wy-form");
    if(mark && form && mark.nextElementSibling!==form){
      s.insertBefore(form, mark.nextSibling);
    }
    if(!$("fbCreate")){
      var c=document.createElement("button");
      c.id="fbCreate"; c.type="button"; c.textContent="Create new account";
      c.onclick=function(){ if(typeof switchAuth==="function") switchAuth("signup"); };
      s.appendChild(c);
    }
    if(!$("fbMeta")){
      var m=document.createElement("div");
      m.id="fbMeta"; m.textContent="Own Club";
      s.appendChild(m);
    }
    var loginBtn=s.querySelector("#loginForm .wy-primary, #loginForm .btn, #loginForm button[type=submit], #loginForm button[type=button]");
    if(loginBtn) loginBtn.textContent="Log in";
    var email=s.querySelector("#loginForm input[type=email], #loginForm input[type=text]");
    if(email) email.placeholder="Mobile number or email";
    var pass=$("loginPass")||s.querySelector("#loginForm input[type=password]");
    if(pass) pass.placeholder="Password";
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", restyle);
  else restyle();
  setTimeout(restyle, 40);
  setTimeout(restyle, 280);
  setTimeout(restyle, 800);
})();
