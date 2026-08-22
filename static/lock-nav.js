(function(){
  function hideWall(){
    var sels=[".space-bg",".warp-img",".warp-stars","#particleCanvas","#leagueFx",".league-fx",".ucl-stars",".ucl-title"];
    for(var s=0;s<sels.length;s++){
      document.querySelectorAll(sels[s]).forEach(function(el){
        el.style.setProperty("display","none","important");
        el.style.setProperty("opacity","0","important");
        el.style.setProperty("visibility","hidden","important");
      });
    }
  }
  function lock(){
    hideWall();
    document.documentElement.style.setProperty("background","#07140f","important");
    document.body.style.setProperty("background","#07140f","important");
    document.body.style.setProperty("overflow","hidden","important");
    var app=document.getElementById("mainApp") || document.querySelector(".app");
    if(app){
      ["position:fixed","top:0","left:0","right:0","bottom:56px","width:100%","max-width:none","overflow-y:auto","overflow-x:hidden","background:#07140f","z-index:2","margin:0","transform:none"].forEach(function(r){
        var p=r.split(":"); app.style.setProperty(p[0], p[1], "important");
      });
    }
    document.querySelectorAll(".page,#home,#market,#machines,#team,#my,#account").forEach(function(el){
      el.style.setProperty("background","#07140f","important");
      el.style.setProperty("width","100%","important");
      el.style.setProperty("max-width","none","important");
    });
    var n=document.querySelector("nav.bottom");
    if(n){
      if(n.parentElement!==document.body) document.body.appendChild(n);
      ["position:fixed","left:0","right:0","bottom:0","top:auto","width:100%","max-width:none","margin:0","height:56px","z-index:2147483647","background:#0b0d10","transform:none"].forEach(function(r){
        var p=r.split(":"); n.style.setProperty(p[0], p[1], "important");
      });
      if(document.body.classList.contains("auth-open")){
        n.style.setProperty("display","none","important");
      } else {
        n.style.setProperty("display","flex","important");
      }
    }
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", lock);
  else lock();
  setTimeout(lock, 150);
  setTimeout(lock, 800);
  window.addEventListener("resize", lock);
  document.addEventListener("click", function(){ setTimeout(lock, 50); }, true);
})();
