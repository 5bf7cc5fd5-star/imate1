#!/usr/bin/env python3
"""Ensure Market tab always has 32 live clubs after HTML assemble."""
from pathlib import Path

SEED = r'''
<script id="club-market-seed">
window.CLUB_MARKET_SEED = [
  {id:1,code:"Manchester City",name:"Manchester City Shares",league:"Premier League",marketValue:"$5.0B",photo:"https://crests.football-data.org/65.png"},
  {id:2,code:"Arsenal",name:"Arsenal Shares",league:"Premier League",marketValue:"$3.5B",photo:"https://crests.football-data.org/57.png"},
  {id:3,code:"Liverpool",name:"Liverpool Shares",league:"Premier League",marketValue:"$5.3B",photo:"https://crests.football-data.org/64.png"},
  {id:4,code:"Chelsea",name:"Chelsea Shares",league:"Premier League",marketValue:"$3.1B",photo:"https://crests.football-data.org/61.png"},
  {id:5,code:"Manchester United",name:"Manchester United Shares",league:"Premier League",marketValue:"$6.0B",photo:"https://crests.football-data.org/66.png"},
  {id:6,code:"Tottenham Hotspur",name:"Tottenham Shares",league:"Premier League",marketValue:"$2.8B",photo:"https://crests.football-data.org/73.png"},
  {id:7,code:"Real Madrid",name:"Real Madrid Shares",league:"La Liga",marketValue:"$6.6B",photo:"https://crests.football-data.org/86.png"},
  {id:8,code:"FC Barcelona",name:"Barcelona Shares",league:"La Liga",marketValue:"$5.5B",photo:"https://crests.football-data.org/81.png"},
  {id:9,code:"Atletico Madrid",name:"Atletico Shares",league:"La Liga",marketValue:"$1.6B",photo:"https://crests.football-data.org/78.png"},
  {id:10,code:"Athletic Club",name:"Athletic Club Shares",league:"La Liga",marketValue:"$0.90B",photo:"https://crests.football-data.org/77.png"},
  {id:11,code:"Real Sociedad",name:"Real Sociedad Shares",league:"La Liga",marketValue:"$0.55B",photo:"https://crests.football-data.org/92.png"},
  {id:12,code:"Villarreal CF",name:"Villarreal Shares",league:"La Liga",marketValue:"$0.42B",photo:"https://crests.football-data.org/94.png"},
  {id:13,code:"Juventus",name:"Juventus Shares",league:"Serie A",marketValue:"$2.0B",photo:"https://crests.football-data.org/109.png"},
  {id:14,code:"Inter Milan",name:"Inter Milan Shares",league:"Serie A",marketValue:"$1.3B",photo:"https://crests.football-data.org/108.png"},
  {id:15,code:"AC Milan",name:"AC Milan Shares",league:"Serie A",marketValue:"$1.4B",photo:"https://crests.football-data.org/98.png"},
  {id:16,code:"SSC Napoli",name:"Napoli Shares",league:"Serie A",marketValue:"$0.85B",photo:"https://crests.football-data.org/113.png"},
  {id:17,code:"Paris Saint-Germain",name:"PSG Shares",league:"Ligue 1",marketValue:"$4.4B",photo:"https://crests.football-data.org/524.png"},
  {id:18,code:"Olympique Marseille",name:"Marseille Shares",league:"Ligue 1",marketValue:"$0.48B",photo:"https://crests.football-data.org/516.png"},
  {id:19,code:"Bayern Munich",name:"Bayern Shares",league:"Bundesliga",marketValue:"$5.1B",photo:"https://crests.football-data.org/5.png"},
  {id:20,code:"Borussia Dortmund",name:"Dortmund Shares",league:"Bundesliga",marketValue:"$2.0B",photo:"https://crests.football-data.org/4.png"},
  {id:21,code:"Al Hilal",name:"Al Hilal Shares",league:"Saudi Pro League",marketValue:"$0.90B",photo:"https://crests.football-data.org/65.png"},
  {id:22,code:"Al Nassr",name:"Al Nassr Shares",league:"Saudi Pro League",marketValue:"$0.75B",photo:"https://crests.football-data.org/66.png"},
  {id:23,code:"Al Ittihad",name:"Al Ittihad Shares",league:"Saudi Pro League",marketValue:"$0.55B",photo:"https://crests.football-data.org/61.png"},
  {id:24,code:"Al Ahli",name:"Al Ahli Shares",league:"Saudi Pro League",marketValue:"$0.50B",photo:"https://crests.football-data.org/57.png"},
  {id:25,code:"Inter Miami CF",name:"Inter Miami Shares",league:"MLS",marketValue:"$1.1B",photo:"https://crests.football-data.org/81.png"},
  {id:26,code:"Los Angeles FC",name:"LAFC Shares",league:"MLS",marketValue:"$1.0B",photo:"https://crests.football-data.org/86.png"},
  {id:27,code:"LA Galaxy",name:"LA Galaxy Shares",league:"MLS",marketValue:"$0.60B",photo:"https://crests.football-data.org/73.png"},
  {id:28,code:"Atlanta United FC",name:"Atlanta United Shares",league:"MLS",marketValue:"$0.70B",photo:"https://crests.football-data.org/64.png"},
  {id:29,code:"Leicester City",name:"Leicester Shares",league:"Championship",marketValue:"$0.45B",photo:"https://crests.football-data.org/338.png"},
  {id:30,code:"Leeds United",name:"Leeds Shares",league:"Championship",marketValue:"$0.40B",photo:"https://crests.football-data.org/341.png"},
  {id:31,code:"Southampton FC",name:"Southampton Shares",league:"Championship",marketValue:"$0.38B",photo:"https://crests.football-data.org/340.png"},
  {id:32,code:"Ipswich Town",name:"Ipswich Shares",league:"Championship",marketValue:"$0.25B",photo:"https://crests.football-data.org/349.png"}
];
if(!window.machines || !window.machines.length){
  window.machines = window.CLUB_MARKET_SEED;
}
try{ if(typeof startMarketFeed==="function") startMarketFeed(); }catch(e){}
setTimeout(function(){ try{ if(typeof startMarketFeed==="function") startMarketFeed(); if(typeof renderMarketList==="function") renderMarketList(); }catch(e){} }, 300);
</script>
'''

FIX = r'''
<script id="market-hard-fix">
(function(){
  function usd(mv){
    if(typeof mv==="number") return mv;
    var s=String(mv||"").replace(/[^0-9.BMKbm]/g,"").toUpperCase();
    var n=parseFloat(s); if(isNaN(n)) n=1e9;
    if(s.indexOf("B")>=0) return n*1e9;
    if(s.indexOf("M")>=0) return n*1e6;
    if(s.indexOf("K")>=0) return n*1e3;
    return n;
  }
  function fmt(n){
    if(n>=1e9) return "$"+(n/1e9).toFixed(2)+"B";
    if(n>=1e6) return "$"+(n/1e6).toFixed(2)+"M";
    if(n>=1e3) return "$"+(n/1e3).toFixed(1)+"K";
    return "$"+n.toFixed(0);
  }
  function list(){
    if(window.machines && window.machines.length) return window.machines;
    return window.CLUB_MARKET_SEED || [];
  }
  window.mktState = window.mktState || {};
  function ensure(){
    var arr=list();
    for(var i=0;i<arr.length;i++){
      var m=arr[i]; if(!m||m.id==null) continue;
      if(window.mktState[m.id]) continue;
      var base=usd(m.marketValue), hist=[], p=base;
      for(var h=0;h<24;h++){ p=p*(1+(Math.random()-0.48)*0.012); hist.push(p); }
      window.mktState[m.id]={base:base,price:p,open:base,hist:hist,chg:((p-base)/base)*100};
    }
  }
  function spark(hist,up){
    if(!hist||hist.length<2) return "";
    var min=Math.min.apply(null,hist), max=Math.max.apply(null,hist), range=(max-min)||1;
    var w=72,h=28,pad=2,pts=[];
    for(var i=0;i<hist.length;i++){
      var x=pad+(i/(hist.length-1))*(w-pad*2);
      var y=h-pad-((hist[i]-min)/range)*(h-pad*2);
      pts.push(x.toFixed(1)+","+y.toFixed(1));
    }
    return '<svg viewBox="0 0 '+w+' '+h+'" preserveAspectRatio="none"><polyline fill="none" stroke="'+(up?"#00c853":"#ff5252")+'" stroke-width="1.8" stroke-linejoin="round" points="'+pts.join(" ")+'"/></svg>';
  }
  function paint(){
    var box=document.getElementById("marketList");
    if(!box) return;
    ensure();
    var q=((document.getElementById("mktSearch")||{}).value||"").trim().toLowerCase();
    var filt=window.mktFilter||"all";
    var arr=list(), rows=[];
    for(var i=0;i<arr.length;i++){
      var m=arr[i], s=window.mktState[m.id];
      if(!s) continue;
      if(q && (String(m.code||"")+" "+String(m.league||"")).toLowerCase().indexOf(q)<0) continue;
      if(filt==="gainers" && s.chg<0) continue;
      if(filt==="losers" && s.chg>0) continue;
      rows.push({m:m,s:s});
    }
    rows.sort(function(a,b){ return Math.abs(b.s.chg)-Math.abs(a.s.chg); });
    var html='<div class="mkt-live"><i></i> LIVE \u00b7 '+rows.length+' clubs \u00b7 updates every 2s</div>';
    if(!rows.length) html+='<div class="empty">No clubs match</div>';
    for(var r=0;r<rows.length;r++){
      var m=rows[r].m, s=rows[r].s, up=s.chg>=0;
      html+='<div class="mkt-row" onclick="(window.openBuyFromMarket&&openBuyFromMarket('+m.id+'))||(window.goPage&&goPage(\'machines\'))">'+
        '<img class="mkt-badge" src="'+(m.photo||m.photoFb||'')+'" alt="" onerror="this.style.visibility=\'hidden\'">'+
        '<div><div class="mkt-name">'+(m.code||m.name)+'</div><div class="mkt-sub">'+(m.league||'')+'</div></div>'+
        '<div class="mkt-spark">'+spark(s.hist,up)+'</div>'+
        '<div><div class="mkt-price">'+fmt(s.price)+'</div><div class="mkt-chg '+(up?"up":"down")+'">'+(up?"+":"")+s.chg.toFixed(2)+'%</div></div></div>';
    }
    box.innerHTML=html;
  }
  function tick(){
    ensure();
    Object.keys(window.mktState).forEach(function(id){
      var s=window.mktState[id];
      var drift=(s.base-s.price)/s.base*0.08;
      var shock=(Math.random()-0.5)*0.018;
      s.price=Math.max(s.base*0.82, Math.min(s.base*1.22, s.price*(1+drift+shock)));
      s.hist.push(s.price); if(s.hist.length>28) s.hist.shift();
      s.chg=((s.price-s.open)/s.open)*100;
    });
    paint();
  }
  function start(){
    ensure(); paint();
    if(window.__mktTimer2) clearInterval(window.__mktTimer2);
    window.__mktTimer2=setInterval(tick, 2200);
  }
  window.renderMarketList = paint;
  window.startMarketFeed = start;
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", start);
  else start();
  setTimeout(start, 250);
  setTimeout(start, 900);
})();
</script>
'''

def patch_file(p: Path):
    if not p.exists():
        return
    data = p.read_text(encoding="utf-8", errors="replace")
    changed = False
    if 'id="club-market-seed"' not in data:
        if "</body>" in data:
            data = data.replace("</body>", SEED + "\n</body>", 1)
        else:
            data += SEED
        changed = True
    if 'id="market-hard-fix"' not in data:
        if "</body>" in data:
            data = data.replace("</body>", FIX + "\n</body>", 1)
        else:
            data += FIX
        changed = True
    if changed:
        p.write_text(data, encoding="utf-8")
        print("patched market into", p.name, "len", len(data))
    else:
        print("already patched", p.name)

def main():
    root = Path(__file__).resolve().parent
    for name in ("index.html", "frontend.html"):
        patch_file(root / name)

if __name__ == "__main__":
    main()
