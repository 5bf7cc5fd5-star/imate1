(function(){
  var CSS = "#fbExact{position:fixed;inset:0;z-index:2147483646;background:#1c1c1e;color:#fff;"+
    "font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',sans-serif;overflow:hidden;"+
    "width:100vw;height:100dvh;max-width:none;margin:0;padding:0;}"+
    "#fbExact *{box-sizing:border-box;}"+
    "#fbExact .fb-back{position:absolute;top:12px;left:8px;width:44px;height:44px;border:0;"+
    "background:transparent;color:#fff;font-size:32px;line-height:44px;}"+
    "#fbExact .fb-logo{position:absolute;top:22.9%;left:50%;width:64px;height:64px;margin-left:-32px;"+
    "border-radius:50%;overflow:hidden;background:#000;}"+
    "#fbExact .fb-logo img{width:175%;height:175%;object-fit:cover;object-position:50% 15%;"+
    "margin:-14% 0 0 -38%;display:block;}"+
    "#fbExact .fb-mid{position:absolute;top:41.3%;left:20px;right:20px;max-width:390px;margin:0 auto;}"+
    "#fbExact .fb-field{display:block;width:100%;height:52px;border-radius:12px;border:1px solid #3a3a3c;"+
    "background:#2c2c2e;color:#fff;font-size:17px;padding:0 16px;margin:0 0 12px;outline:none;-webkit-appearance:none;}"+
    "#fbExact .fb-field::placeholder{color:#8e8e93;}"+
    "#fbExact .fb-login{display:block;width:100%;height:48px;border:0;border-radius:24px;"+
    "background:#1877f2;color:#fff;font-size:17px;font-weight:700;margin:2px 0 16px;}"+
    "#fbExact .fb-forgot{display:block;width:100%;border:0;background:none;color:#fff;font-size:16px;font-weight:600;text-align:center;}"+
    "#fbExact .fb-create{position:absolute;left:20px;right:20px;bottom:9.5%;height:44px;max-width:390px;margin:0 auto;"+
    "border-radius:22px;border:1.5px solid #4599ff;background:transparent;color:#4599ff;font-size:16px;font-weight:700;}"+
    "#fbExact .fb-meta{position:absolute;left:0;right:0;bottom:4.4%;text-align:center;color:#fff;font-size:16px;font-weight:700;}"+
    "html.auth-open,body.auth-open{overflow:hidden!important;height:100dvh!important;background:#1c1c1e!important;}"+
    "body.auth-open #mainApp,body.auth-open nav.bottom,body.auth-open .space-bg,body.auth-open .wy-sky{display:none!important;}"+
    "#authScreen{position:fixed!important;inset:0!important;overflow:hidden!important;background:#1c1c1e!important;}"+
    "#authScreen>:not(#fbExact){display:none!important;}";

  function mount(){
    if(document.getElementById("fbExact")) return;
    var s=document.getElementById("authScreen")||document.querySelector(".auth-screen")||document.body;
    if(!document.getElementById("fbExactCss")){
      var st=document.createElement("style");
      st.id="fbExactCss";
      st.appendChild(document.createTextNode(CSS));
      document.head.appendChild(st);
    }
    document.documentElement.classList.add("auth-open");
    document.body.classList.add("auth-open");
    var box=document.createElement("div");
    box.id="fbExact";
    box.innerHTML='<button type="button" class="fb-back" id="fbBackBtn">\u2039</button>'+
      '<div class="fb-logo"><img src="/own-club-logo.jpg" alt="Own Club"></div>'+
      '<div class="fb-mid">'+
      '<input class="fb-field" id="fbId" placeholder="Mobile number or email" autocomplete="username">'+
      '<input class="fb-field" id="fbPass" type="password" placeholder="Password" autocomplete="current-password">'+
      '<button type="button" class="fb-login" id="fbLoginBtn">Log in</button>'+
      '<button type="button" class="fb-forgot" id="fbForgotBtn">Forgot password?</button>'+
      '</div>'+
      '<button type="button" class="fb-create" id="fbCreateBtn">Create new account</button>'+
      '<div class="fb-meta">Own Club</div>';
    s.appendChild(box);
    function copy(){
      var a=document.getElementById("loginId")||document.querySelector("#loginForm input[type=email],#loginForm input[type=text]");
      var b=document.getElementById("loginPass")||document.querySelector("#loginForm input[type=password]");
      if(a) a.value=document.getElementById("fbId").value;
      if(b) b.value=document.getElementById("fbPass").value;
    }
    document.getElementById("fbLoginBtn").onclick=function(){ copy(); if(typeof doLogin==="function") doLogin(); };
    document.getElementById("fbPass").addEventListener("keydown",function(e){ if(e.key==="Enter"){ copy(); if(typeof doLogin==="function") doLogin(); }});
    document.getElementById("fbForgotBtn").onclick=function(){
      if(typeof openForgotPassword==="function") openForgotPassword();
    };
    document.getElementById("fbCreateBtn").onclick=function(){
      if(typeof switchAuth==="function") switchAuth("signup");
    };
    document.getElementById("fbBackBtn").onclick=function(){
      if(typeof switchAuth==="function") switchAuth("login");
    };
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", mount);
  else mount();
  setTimeout(mount, 20);
  setTimeout(mount, 250);
})();
