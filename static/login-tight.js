(function(){
  var CSS = [
    '#fbExact{position:fixed;inset:0;z-index:2147483646;background:#1c1c1e;color:#fff;',
    "font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text','Helvetica Neue',Helvetica,Arial,sans-serif;",
    'overflow:hidden;width:100vw;height:100dvh;max-width:none;margin:0;padding:0;',
    'display:flex;flex-direction:column;align-items:center;}',
    '#fbExact *{box-sizing:border-box;-webkit-tap-highlight-color:transparent;}',
    '#fbExact .fb-back{position:absolute;top:max(10px,env(safe-area-inset-top));left:6px;width:44px;height:44px;',
    'border:0;background:transparent;color:#fff;font-size:34px;line-height:44px;font-weight:300;z-index:2;}',
    '#fbExact .fb-logo{width:88px;height:88px;border-radius:50%;overflow:hidden;background:#000;',
    'margin:56px auto 28px;flex:0 0 88px;box-shadow:0 0 0 0 transparent;}',
    '#fbExact .fb-logo img{width:100%;height:100%;object-fit:contain;object-position:center;display:block;background:#000;}',
    '#fbExact .fb-mid{width:100%;max-width:390px;padding:0 20px;flex:0 0 auto;}',
    '#fbExact .fb-field{display:block;width:100%;height:52px;border-radius:12px;border:1px solid #3a3a3c;',
    'background:#2c2c2e;color:#fff;font-size:17px;line-height:22px;padding:0 16px;margin:0 0 12px;',
    'outline:none;-webkit-appearance:none;font-family:inherit;letter-spacing:-0.2px;}',
    '#fbExact .fb-field::placeholder{color:#8e8e93;font-weight:400;}',
    '#fbExact .fb-login{display:block;width:100%;height:48px;border:0;border-radius:24px;',
    'background:#1877f2;color:#fff;font-size:17px;font-weight:600;margin:4px 0 14px;',
    'font-family:inherit;letter-spacing:-0.2px;}',
    '#fbExact .fb-forgot{display:block;width:100%;border:0;background:none;color:#fff;',
    'font-size:16px;font-weight:600;text-align:center;padding:4px 0;font-family:inherit;letter-spacing:-0.2px;}',
    '#fbExact .fb-gap{flex:1 1 auto;min-height:20px;max-height:48px;}',
    '#fbExact .fb-create{width:calc(100% - 40px);max-width:390px;height:44px;border-radius:22px;',
    'border:1.5px solid #4599ff;background:transparent;color:#4599ff;font-size:16px;font-weight:600;',
    'margin:0 20px;font-family:inherit;letter-spacing:-0.2px;}',
    '#fbExact .fb-meta{text-align:center;color:#fff;font-size:15px;font-weight:700;',
    'margin:14px 0 calc(12px + env(safe-area-inset-bottom));letter-spacing:0.2px;}',
    'html.auth-open,body.auth-open{overflow:hidden!important;height:100dvh!important;background:#1c1c1e!important;margin:0!important;}',
    'body.auth-open #mainApp,body.auth-open nav.bottom,body.auth-open .space-bg,body.auth-open .wy-sky{display:none!important;}',
    '#authScreen{position:fixed!important;inset:0!important;overflow:hidden!important;background:#1c1c1e!important;width:100vw!important;max-width:none!important;}',
    '#authScreen>:not(#fbExact){display:none!important;visibility:hidden!important;}'
  ].join('');

  function mount(){
    if(document.getElementById('fbExact')) return;
    var s=document.getElementById('authScreen')||document.querySelector('.auth-screen')||document.body;
    if(!document.getElementById('fbExactCss')){
      var st=document.createElement('style');
      st.id='fbExactCss';
      st.appendChild(document.createTextNode(CSS));
      document.head.appendChild(st);
    }
    document.documentElement.classList.add('auth-open');
    document.body.classList.add('auth-open');
    var box=document.createElement('div');
    box.id='fbExact';
    box.innerHTML=
      '<button type="button" class="fb-back" id="fbBackBtn" aria-label="Back">\u2039</button>'+
      '<div class="fb-logo"><img src="/own-club-logo.jpg?v=37" alt="Own Club Share"></div>'+
      '<div class="fb-mid">'+
        '<input class="fb-field" id="fbId" placeholder="Mobile number or email" autocomplete="username" inputmode="email">'+
        '<input class="fb-field" id="fbPass" type="password" placeholder="Password" autocomplete="current-password">'+
        '<button type="button" class="fb-login" id="fbLoginBtn">Log in</button>'+
        '<button type="button" class="fb-forgot" id="fbForgotBtn">Forgot password?</button>'+
      '</div>'+
      '<div class="fb-gap" aria-hidden="true"></div>'+
      '<button type="button" class="fb-create" id="fbCreateBtn">Create new account</button>'+
      '<div class="fb-meta">Own Club</div>';
    s.appendChild(box);
    function copy(){
      var a=document.getElementById('loginId')||document.querySelector('#loginForm input[type=email],#loginForm input[type=text]');
      var b=document.getElementById('loginPass')||document.querySelector('#loginForm input[type=password]');
      if(a) a.value=document.getElementById('fbId').value;
      if(b) b.value=document.getElementById('fbPass').value;
    }
    document.getElementById('fbLoginBtn').onclick=function(){ copy(); if(typeof doLogin==='function') doLogin(); };
    document.getElementById('fbPass').addEventListener('keydown',function(e){
      if(e.key==='Enter'){ copy(); if(typeof doLogin==='function') doLogin(); }
    });
    document.getElementById('fbForgotBtn').onclick=function(){
      if(typeof openForgotPassword==='function') openForgotPassword();
    };
    document.getElementById('fbCreateBtn').onclick=function(){
      if(typeof switchAuth==='function') switchAuth('signup');
    };
    document.getElementById('fbBackBtn').onclick=function(){
      if(typeof switchAuth==='function') switchAuth('login');
    };
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', mount);
  else mount();
  setTimeout(mount, 20);
  setTimeout(mount, 200);
})();
