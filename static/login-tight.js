(function(){
  function pack(){
    var s=document.getElementById("authScreen")||document.querySelector(".auth-screen");
    if(!s) return;
    document.documentElement.classList.add("auth-open");
    document.body.classList.add("auth-open");
    s.style.setProperty("height","100dvh","important");
    s.style.setProperty("max-height","100dvh","important");
    s.style.setProperty("overflow","hidden","important");
    s.style.setProperty("display","flex","important");
    s.style.setProperty("flex-direction","column","important");
    s.style.setProperty("justify-content","flex-start","important");
    s.style.setProperty("padding","28px 18px 12px","important");
    s.style.setProperty("gap","0","important");
    var nodes=s.querySelectorAll("*");
    for(var i=0;i<nodes.length;i++){
      var el=nodes[i];
      el.style.setProperty("flex-grow","0","important");
      var tag=el.tagName;
      if(tag==="IMG"||tag==="SVG"||tag==="CANVAS"){
        el.style.setProperty("max-height","56px","important");
        el.style.setProperty("height","56px","important");
        el.style.setProperty("object-fit","contain","important");
      }
    }
    var packEl=document.getElementById("ocPack");
    if(!packEl){
      packEl=document.createElement("div");
      packEl.id="ocPack";
      var move=[];
      var kids=Array.prototype.slice.call(s.children);
      kids.forEach(function(ch){
        if(ch.id==="ocPack") return;
        var cls=(ch.className||"")+" "+(ch.id||"");
        if(/bg|hero|particle|canvas|space/i.test(cls)) {
          ch.style.setProperty("display","none","important");
          return;
        }
        move.push(ch);
      });
      s.insertBefore(packEl, s.firstChild);
      move.forEach(function(ch){ packEl.appendChild(ch); });
    }
    packEl.style.cssText="width:100%;max-width:390px;margin:0 auto;display:flex;flex-direction:column;gap:8px;";
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", pack);
  else pack();
  setTimeout(pack, 30);
  setTimeout(pack, 250);
  setTimeout(pack, 800);
})();
