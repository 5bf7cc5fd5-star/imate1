(function(){
  function $(id){ return document.getElementById(id); }
  function restyle(){
    var s=$("authScreen")||document.querySelector(".auth-screen");
    if(!s) return;
    document.documentElement.classList.add("auth-open");
    document.body.classList.add("auth-open");
    if(!$("fbBack")){
      var b=document.createElement("button");
      b.id="fbBack";
      b.type="button";
      b.setAttribute("aria-label","Back");
      b.textContent="‹";
      b.onclick=function(){
        if(typeof switchAuth==="function"){
          var su=$("signupForm");
          if(su && su.style.display!=="none" && su.offsetParent){ switchAuth("login"); return; }
        }
        if(history.length>1) history.back();
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
      var logo=s.querySelector(".auth-logo,.wy-logo,.brand");
      if(logo && logo.parentNode) logo.parentNode.insertBefore(w, logo);
      else s.insertBefore(w, s.children[1]||null);
    }
    if(!$("fbCreate")){
      var c=document.createElement("button");
      c.id="fbCreate";
      c.type="button";
      c.textContent="Create new account";
      c.onclick=function(){ if(typeof switchAuth==="function") switchAuth("signup"); };
      s.appendChild(c);
    }
    if(!$("fbMeta")){
      var m=document.createElement("div");
      m.id="fbMeta";
      m.textContent="Own Club";
      s.appendChild(m);
    }
    var hideSel=s.querySelectorAll(".auth-logo h1,.auth-logo p,.wy-brand-text,canvas,.auth-bg");
    for(var i=0;i<hideSel.length;i++) hideSel[i].style.setProperty("display","none","important");
    var loginBtn=s.querySelector("#loginForm button.wy-primary, #loginForm .btn, #loginForm button[type=button], #loginForm button[type=submit]");
    if(loginBtn && /sign|log/i.test(loginBtn.textContent||"")) loginBtn.textContent="Log in";
    var forgot=s.querySelector("#loginForm .wy-muted button, button.wy-link");
    if(forgot && /need an account|sign up/i.test(forgot.textContent||"")){
      forgot.textContent="Forgot password?";
      forgot.onclick=function(){ if(typeof switchAuth==="function") switchAuth("forgot"); else if(typeof openForgot==="function") openForgot(); };
    }
    var email=s.querySelector("#loginForm input[type=email], #loginForm input[type=text], #loginEmail, #loginUser");
    if(email) email.setAttribute("placeholder","Mobile number or email");
    var pass=$("loginPass")||s.querySelector("#loginForm input[type=password]");
    if(pass) pass.setAttribute("placeholder","Password");
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", restyle);
  else restyle();
  setTimeout(restyle, 40);
  setTimeout(restyle, 300);
  setTimeout(restyle, 900);
})();
