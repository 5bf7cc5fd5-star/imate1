(function(){
  function mount(){
    var s=document.getElementById("authScreen")||document.querySelector(".auth-screen");
    if(!s) return;
    document.body.classList.add("auth-open");
    if(document.getElementById("fbExact")) return;
    var box=document.createElement("div");
    box.id="fbExact";
    box.innerHTML='
      <button type="button" class="fb-back" id="fbBackBtn" aria-label="Back">\u2039</button>
      <div class="fb-mid">
        <div class="fb-logo"><img src="/own-club-logo.jpg" alt="Own Club"></div>
        <input class="fb-field" id="fbId" placeholder="Mobile number or email" autocomplete="username">
        <input class="fb-field" id="fbPass" type="password" placeholder="Password" autocomplete="current-password">
        <button type="button" class="fb-login" id="fbLoginBtn">Log in</button>
        <button type="button" class="fb-forgot" id="fbForgotBtn">Forgot password?</button>
      </div>
      <div class="fb-spacer"></div>
      <button type="button" class="fb-create" id="fbCreateBtn">Create new account</button>
      <div class="fb-meta">Own Club</div>';
    s.appendChild(box);
    function copy(){
      var a=document.getElementById("loginId")||document.getElementById("loginEmail")||document.querySelector("#loginForm input[type=email],#loginForm input[type=text]");
      var b=document.getElementById("loginPass")||document.querySelector("#loginForm input[type=password]");
      if(a) a.value=document.getElementById("fbId").value;
      if(b) b.value=document.getElementById("fbPass").value;
    }
    document.getElementById("fbLoginBtn").onclick=function(){
      copy();
      if(typeof doLogin==="function") doLogin();
    };
    document.getElementById("fbPass").addEventListener("keydown", function(e){
      if(e.key==="Enter"){ copy(); if(typeof doLogin==="function") doLogin(); }
    });
    document.getElementById("fbForgotBtn").onclick=function(){
      box.classList.add("hidden");
      if(typeof openForgotPassword==="function") openForgotPassword();
    };
    document.getElementById("fbCreateBtn").onclick=function(){
      box.classList.add("hidden");
      if(typeof switchAuth==="function") switchAuth("signup");
    };
    document.getElementById("fbBackBtn").onclick=function(){
      if(typeof switchAuth==="function") switchAuth("login");
      box.classList.remove("hidden");
    };
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", mount);
  else mount();
  setTimeout(mount, 50);
  setTimeout(mount, 400);
})();
