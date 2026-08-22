(function(){
  function lock(){
    var n=document.querySelector("nav.bottom");
    if(n){
      if(n.parentElement!==document.body) document.body.appendChild(n);
      ["position:fixed","left:0","right:0","bottom:0","top:auto","width:100%","max-width:none","margin:0","padding:0","transform:none","z-index:2147483647","background:#0b0d10"].forEach(function(r){
        var p=r.split(":");
        n.style.setProperty(p[0], p[1], "important");
      });
    }
    document.querySelectorAll(".space-bg,.space-bg .warp,.space-bg .warp-img").forEach(function(el){
      el.style.setProperty("display","none","important");
      el.style.setProperty("opacity","0","important");
    });
    ["html","body","#mainApp",".app","#market",".page.active"].forEach(function(sel){
      var els=sel==="html"?[document.documentElement]:sel==="body"?[document.body]:document.querySelectorAll(sel);
      for(var i=0;i<els.length;i++){
        els[i].style.setProperty("background","#07140f","important");
        els[i].style.setProperty("width","100%","important");
        els[i].style.setProperty("max-width","none","important");
      }
    });
    var app=document.getElementById("mainApp");
    if(app){
      app.style.setProperty("min-height","100dvh","important");
      app.style.setProperty("padding-bottom","64px","important");
    }
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", lock);
  else lock();
  setTimeout(lock, 200);
  setTimeout(lock, 900);
  window.addEventListener("resize", lock);
})();
