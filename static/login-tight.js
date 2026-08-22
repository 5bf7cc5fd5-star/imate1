(function(){
  var LOGO = "/static/own-club-logo.jpg?v=48";
  var CSS = [
    '#fbExact{position:fixed;inset:0;z-index:2147483646;background:#1c1c1e;color:#fff;',
    "font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text','Helvetica Neue',Helvetica,Arial,sans-serif;",
    'overflow:hidden;width:100vw;height:100dvh;margin:0;padding:0;display:flex;flex-direction:column;align-items:center;}',
    '#fbExact *{box-sizing:border-box;-webkit-tap-highlight-color:transparent;}',
    '#fbExact .fb-back{position:absolute;top:max(10px,env(safe-area-inset-top));left:6px;width:44px;height:44px;',
    'border:0;background:transparent;color:#4a90d9;font-size:34px;line-height:44px;font-weight:300;z-index:2;}',
    '#fbExact .fb-logo{width:96px;height:96px;border-radius:50%;overflow:hidden;background:#111;margin:48px auto 22px;flex:0 0 96px;}',
    '#fbExact .fb-logo img{width:100%;height:100%;object-fit:contain;object-position:center;display:block;}',
    '#fbExact .fb-mid{width:100%;max-width:390px;padding:0 22px;flex:0 0 auto;}',
    '#fbExact .fb-field{display:block;width:100%;height:52px;border-radius:12px;border:1px solid #3a3a3c;',
    'background:#2c2c2e;color:#fff;font-size:17px;padding:0 16px;margin:0 0 12px;outline:none;font-family:inherit;}',
    '#fbExact .fb-field::placeholder{color:#8e8e93;}',
    '#fbExact .fb-login{display:block;width:100%;height:48px;border:0;border-radius:24px;background:#1877f2;color:#fff;font-size:17px;font-weight:600;margin:4px 0 12px;font-family:inherit;}',
    '#fbExact .fb-forgot{display:block;width:100%;border:0;background:none;color:#8ab4f8;font-size:16px;font-weight:600;text-align:center;padding:2px 0;font-family:inherit;}',
    '#fbExact .fb-gap{flex:0 0 16px;height:16px;min-height:16px;max-height:16px;}',
    '#fbExact .fb-create{width:calc(100% - 44px);max-width:390px;height:44px;border-radius:22px;border:1.5px solid #4599ff;background:transparent;color:#4599ff;font-size:16px;font-weight:600;margin:0 22px;font-family:inherit;}',
    '#fbExact .fb-meta{text-align:center;color:#fff;font-size:15px;font-weight:700;margin:12px 0 calc(10px + env(safe-area-inset-bottom));}',
    '#authScreen.hidden,#fbExact.hidden{display:none!important;visibility:hidden!important;pointer-events:none!important;}',
    '#mainApp:not(.hidden){display:block!important;}',
    '#mainApp:not(.hidden) nav.bottom{display:flex!important;position:fixed!important;left:0!important;right:0!important;bottom:0!important;z-index:10080!important;}'
  ].join('');
  function teardown(){
    var box=document.getElementById('fbExact');
    if(box) box.remove();
    var auth=document.getElementById('authScreen');
    if(auth){ auth.classList.add('hidden'); auth.style.setProperty('display','none','important'); }
    document.documentElement.classList.remove('auth-open');
    document.body.classList.remove('auth-open');
    var main=document.getElementById('mainApp');
    if(main){ main.classList.remove('hidden'); main.style.setProperty('display','block','important'); }
  }
  function mount(){
    var s=document.getElementById('authScreen')||document.body;
    if(document.getElementById('fbExact')) return;
    if(s.classList && s.classList.contains('hidden')) return;
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
      '<div class="fb-logo"><img src="'+LOGO+'" alt="Own Club"></div>'+
      '<div class="fb-mid">'+
        '<input class="fb-field" id="fbId" placeholder="Mobile number or email" autocomplete="username">'+
        '<input class="fb-field" id="fbPass" type="password" placeholder="Password" autocomplete="current-password">'+
        '<button type="button" class="fb-login" id="fbLoginBtn">Log in</button>'+
        '<button type="button" class="fb-forgot" id="fbForgotBtn">Forgot password?</button>'+
      '</div>'+
      '<div class="fb-gap"></div>'+
      '<button type="button" class="fb-create" id="fbCreateBtn">Create new account</button>'+
      '<div class="fb-meta">Own Club</div>';
    s.appendChild(box);
    function copy(){
      var a=document.getElementById('loginId')||document.querySelector('#loginForm input[type=email],#loginForm input[type=text]');
      var b=document.getElementById('loginPass')||document.querySelector('#loginForm input[type=password]');
      if(a) a.value=document.getElementById('fbId').value;
      if(b) b.value=document.getElementById('fbPass').value;
    }
    document.getElementById('fbLoginBtn').onclick=function(){
      copy();
      if(typeof doLogin==='function') doLogin();
      setTimeout(function(){
        var main=document.getElementById('mainApp');
        if(main && !main.classList.contains('hidden')) teardown();
      }, 80);
    };
    document.getElementById('fbPass').addEventListener('keydown',function(e){
      if(e.key==='Enter') document.getElementById('fbLoginBtn').click();
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
    var _show = window.showApp;
    if(typeof _show==='function' && !_show._fbWrapped){
      window.showApp=function(){
        var r=_show.apply(this, arguments);
        try{
          var main=document.getElementById('mainApp');
          if(main && !main.classList.contains('hidden')) teardown();
        }catch(e){}
        return r;
      };
      window.showApp._fbWrapped=true;
    }
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', mount);
  else mount();
  setTimeout(mount, 30);
})();
