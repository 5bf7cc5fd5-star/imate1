(function(){
  function tight(){
    var s=document.getElementById("authScreen")||document.querySelector(".auth-screen");
    if(!s) return;
    s.style.setProperty("justify-content","flex-start","important");
    s.style.setProperty("gap","0","important");
    s.style.setProperty("padding-top","48px","important");
    var kids=s.querySelectorAll(".auth-center,.auth-card,.auth-logo,.tabs,form");
    for(var i=0;i<kids.length;i++){
      kids[i].style.setProperty("margin-top","0","important");
      kids[i].style.setProperty("margin-bottom","10px","important");
      kids[i].style.setProperty("min-height","0","important");
    }
    var spacers=s.querySelectorAll(".auth-bg,.auth-hero,.spacer,[style*='flex:1'],[style*='flex: 1']");
    for(var j=0;j<spacers.length;j++){
      spacers[j].style.setProperty("display","none","important");
      spacers[j].style.setProperty("flex","0","important");
      spacers[j].style.setProperty("height","0","important");
    }
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", tight);
  else tight();
  setTimeout(tight, 50);
  setTimeout(tight, 400);
})();
