/* Pin tab bar to the viewport so page scroll never moves it */
(function(){
  function lock(){
    var n=document.querySelector("nav.bottom");
    if(!n) return;
    if(n.parentElement!==document.body){
      document.body.appendChild(n);
    }
    n.style.setProperty("position","fixed","important");
    n.style.setProperty("left","0","important");
    n.style.setProperty("right","0","important");
    n.style.setProperty("bottom","0","important");
    n.style.setProperty("top","auto","important");
    n.style.setProperty("width","100vw","important");
    n.style.setProperty("margin","0","important");
    n.style.setProperty("padding","0","important");
    n.style.setProperty("transform","none","important");
    n.style.setProperty("z-index","2147483647","important");
  }
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", lock);
  else lock();
  setTimeout(lock, 200);
  setTimeout(lock, 800);
  window.addEventListener("resize", lock);
})();
