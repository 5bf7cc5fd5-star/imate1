(function(){
  /* X + Back rules (SPA)
     1) X closes only the open sheet/modal (deposit, withdraw, buy, account, chat).
        Does not submit. Does not log out. Fields stay until they submit.
     2) Phone / browser Back: close top sheet first.
     3) If no sheet: go to previous tab (Market/Shares/Team/Account -> Home).
     4) On Home with no sheet: stay in the app (do not leave ownclubshares.co).
     5) Withdraw / deposit still follow Aug 15 rules only when the user taps Submit.
  */
  var stack = ["home"];
  var pushing = false;

  function visible(el){
    if(!el) return false;
    var s = window.getComputedStyle(el);
    if(s.display==="none" || s.visibility==="hidden" || s.opacity==="0") return false;
    if(el.classList && (el.classList.contains("hidden") || el.classList.contains("hide"))) return false;
    var r = el.getBoundingClientRect();
    return r.width>2 && r.height>2;
  }

  function sheets(){
    var nodes = document.querySelectorAll(
      ".modal, .sheet, .drawer, .popup, [id$='Modal'], [id$='Sheet'], [class*='modal'], [class*='overlay']"
    );
    var out=[];
    for(var i=0;i<nodes.length;i++){
      if(visible(nodes[i]) && nodes[i].id!=="authScreen" && nodes[i].id!=="mainApp") out.push(nodes[i]);
    }
    return out;
  }

  function closeTopSheet(){
    var list = sheets();
    if(!list.length) return false;
    var el = list[list.length-1];
    var id = el.id || "";
    if(id && typeof window.closeModal==="function"){
      try{ window.closeModal(id); return true; }catch(e){}
    }
    el.classList.add("hidden");
    el.style.setProperty("display","none","important");
    el.style.setProperty("visibility","hidden","important");
    return true;
  }

  function currentPage(){
    var on = document.querySelector(".page.active, section.page.on, section.page[style*='display: block']");
    if(on && on.id) return on.id;
    var act = document.querySelector("nav.bottom .nav.active");
    if(act){
      var p = act.getAttribute("data-page");
      if(p) return p;
    }
    return stack[stack.length-1] || "home";
  }

  function goPrevTab(){
    var here = currentPage();
    if(here && here!=="home" && typeof window.goPage==="function"){
      window.goPage("home");
      return true;
    }
    if(stack.length>1){
      stack.pop();
      var prev = stack[stack.length-1] || "home";
      if(typeof window.goPage==="function") window.goPage(prev);
      return true;
    }
    return false;
  }

  function handleBack(){
    if(closeTopSheet()) return true;
    if(goPrevTab()) return true;
    return false;
  }

  function hookGoPage(){
    if(typeof window.goPage!=="function" || window.goPage.__ocHooked) return;
    var orig = window.goPage;
    window.goPage = function(p){
      var cur = currentPage();
      if(p && p!==cur){
        if(stack[stack.length-1]!==cur) stack.push(cur);
        stack.push(p);
        if(stack.length>12) stack = stack.slice(-8);
      }
      pushing = true;
      try{ history.pushState({oc:true, page:p}, "", "#"+p); }catch(e){}
      pushing = false;
      return orig.apply(this, arguments);
    };
    window.goPage.__ocHooked = true;
  }

  function wireX(){
    document.querySelectorAll(
      ".modal .close, .modal .x, [data-close], .sheet-close, .modal-close, button.close"
    ).forEach(function(btn){
      if(btn.__ocX) return;
      btn.__ocX = true;
      btn.addEventListener("click", function(ev){
        ev.preventDefault();
        ev.stopPropagation();
        var box = btn.closest(".modal, .sheet, .drawer, .popup, [id$='Modal']") || btn.parentElement;
        var id = box && box.id;
        if(id && typeof window.closeModal==="function") window.closeModal(id);
        else closeTopSheet();
      }, true);
    });
  }

  window.addEventListener("popstate", function(ev){
    if(pushing) return;
    var kept = handleBack();
    if(kept){
      try{ history.pushState({oc:true}, "", location.hash || "#home"); }catch(e){}
    }
  });

  document.addEventListener("keydown", function(e){
    if(e.key==="Escape"){
      if(handleBack()) e.preventDefault();
    }
  });

  try{
    history.replaceState({oc:true, page:"home"}, "", location.hash || "#home");
    history.pushState({oc:true, page:"home"}, "", location.hash || "#home");
  }catch(e){}

  function boot(){
    hookGoPage();
    wireX();
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
  setTimeout(boot, 400);
  setTimeout(boot, 1200);
  window.ocHandleBack = handleBack;
  window.ocCloseSheet = closeTopSheet;
})();
