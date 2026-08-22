/* Own Club — live market seed + feed (always fills #marketList) */
(function(){
  function usdFromLabel(mv){
    if(typeof mv === "number") return mv;
    var s = String(mv||"").replace(/[^0-9.BMKbm]/g,"").toUpperCase();
    var n = parseFloat(s);
    if(isNaN(n)) return 1e9;
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
  var FALLBACK = [
    {id:1,code:"Manchester City",league:"Premier League",marketValue:"$5.0B",photo:"https://crests.football-data.org/65.png"},
    {id:2,code:"Arsenal",league:"Premier League",marketValue:"$3.5B",photo:"https://crests.football-data.org/57.png"},
    {id:3,code:"Liverpool",league:"Premier League",marketValue:"$5.3B",photo:"https://crests.football-data.org/64.png"},
    {id:4,code:"Chelsea",league:"Premier League",marketValue:"$3.1B",photo:"https://crests.football-data.org/61.png"},
    {id:5,code:"Manchester United",league:"Premier League",marketValue:"$6.0B",photo:"https://crests.football-data.org/66.png"},
    {id:6,code:"Tottenham",league:"Premier League",marketValue:"$2.8B",photo:"https://crests.football-data.org/73.png"},
    {id:7,code:"Real Madrid",league:"La Liga",marketValue:"$6.6B",photo:"https://crests.football-data.org/86.png"},
    {id:8,code:"Barcelona",league:"La Liga",marketValue:"$5.5B",photo:"https://crests.football-data.org/81.png"},
    {id:9,code:"Atletico Madrid",league:"La Liga",marketValue:"$1.6B",photo:"https://crests.football-data.org/78.png"},
    {id:10,code:"Sevilla",league:"La Liga",marketValue:"$0.45B",photo:"https://crests.football-data.org/559.png"},
    {id:11,code:"Villarreal",league:"La Liga",marketValue:"$0.42B",photo:"https://crests.football-data.org/94.png"},
    {id:12,code:"Real Sociedad",league:"La Liga",marketValue:"$0.55B",photo:"https://crests.football-data.org/92.png"},
    {id:13,code:"Juventus",league:"Serie A",marketValue:"$2.0B",photo:"https://crests.football-data.org/109.png"},
    {id:14,code:"Inter Milan",league:"Serie A",marketValue:"$1.3B",photo:"https://crests.football-data.org/108.png"},
    {id:15,code:"AC Milan",league:"Serie A",marketValue:"$1.4B",photo:"https://crests.football-data.org/98.png"},
    {id:16,code:"Napoli",league:"Serie A",marketValue:"$0.85B",photo:"https://crests.football-data.org/113.png"},
    {id:17,code:"PSG",league:"Ligue 1",marketValue:"$4.4B",photo:"https://crests.football-data.org/524.png"},
    {id:18,code:"Marseille",league:"Ligue 1",marketValue:"$0.48B",photo:"https://crests.football-data.org/516.png"},
    {id:19,code:"Bayern Munich",league:"Bundesliga",marketValue:"$5.1B",photo:"https://crests.football-data.org/5.png"},
    {id:20,code:"Borussia Dortmund",league:"Bundesliga",marketValue:"$2.0B",photo:"https://crests.football-data.org/4.png"},
    {id:21,code:"Al Hilal",league:"Saudi Pro League",marketValue:"$0.90B",photo:"https://crests.football-data.org/7466.png"},
    {id:22,code:"Al Nassr",league:"Saudi Pro League",marketValue:"$0.75B",photo:"https://crests.football-data.org/7491.png"},
    {id:23,code:"Al Ittihad",league:"Saudi Pro League",marketValue:"$0.55B",photo:"https://crests.football-data.org/7476.png"},
    {id:24,code:"Al Ahli",league:"Saudi Pro League",marketValue:"$0.50B",photo:"https://crests.football-data.org/7468.png"},
    {id:25,code:"Inter Miami",league:"MLS",marketValue:"$1.1B",photo:"https://crests.football-data.org/8130.png"},
    {id:26,code:"LA Galaxy",league:"MLS",marketValue:"$0.60B",photo:"https://crests.football-data.org/746.png"},
    {id:27,code:"LAFC",league:"MLS",marketValue:"$1.0B",photo:"https://crests.football-data.org/8129.png"},
    {id:28,code:"Atlanta United",league:"MLS",marketValue:"$0.70B",photo:"https://crests.football-data.org/8110.png"},
    {id:29,code:"Leicester City",league:"Championship",marketValue:"$0.45B",photo:"https://crests.football-data.org/338.png"},
    {id:30,code:"Leeds United",league:"Championship",marketValue:"$0.40B",photo:"https://crests.football-data.org/341.png"},
    {id:31,code:"Southampton",league:"Championship",marketValue:"$0.38B",photo:"https://crests.football-data.org/340.png"},
    {id:32,code:"Ipswich Town",league:"Championship",marketValue:"$0.25B",photo:"https://crests.football-data.org/349.png"}
  ];

  window.__mktFeed = window.__mktFeed || {};
  var st = window.__mktFeed;

  function clubs(){
    if(window.machines && window.machines.length){
      return window.machines.map(function(m){
        return {
          id: m.id,
          code: m.code || m.name,
          league: m.league || "",
          marketValue: m.marketValue,
          photo: m.photo || m.photoFb || ""
        };
      });
    }
    if(window.CLUB_MARKET_SEED && window.CLUB_MARKET_SEED.length) return window.CLUB_MARKET_SEED;
    return FALLBACK;
  }

  function ensure(){
    var list = clubs();
    for(var i=0;i<list.length;i++){
      var c = list[i];
      if(st[c.id]) continue;
      var base = usdFromLabel(c.marketValue);
      var hist=[], p=base;
      for(var h=0;h<24;h++){ p = p*(1+(Math.random()-0.48)*0.012); hist.push(p); }
      st[c.id] = {base:base, price:p, open:base, hist:hist, chg:((p-base)/base)*100};
    }
  }

  function spark(hist, up){
    if(!hist || hist.length<2) return "";
    var min=Math.min.apply(null,hist), max=Math.max.apply(null,hist), range=(max-min)||1;
    var w=72,h=28,pad=2,pts=[];
    for(var i=0;i<hist.length;i++){
      var x=pad+(i/(hist.length-1))*(w-pad*2);
      var y=h-pad-((hist[i]-min)/range)*(h-pad*2);
      pts.push(x.toFixed(1)+","+y.toFixed(1));
    }
    return '<svg viewBox="0 0 '+w+' '+h+'" preserveAspectRatio="none"><polyline fill="none" stroke="'+(up?"#00c853":"#ff5252")+'" stroke-width="1.8" stroke-linejoin="round" points="'+pts.join(" ")+'"/></svg>';
  }

  function tick(){
    ensure();
    Object.keys(st).forEach(function(id){
      var s=st[id];
      var drift=(s.base-s.price)/s.base*0.08;
      var shock=(Math.random()-0.5)*0.018;
      s.price=Math.max(s.base*0.82, Math.min(s.base*1.22, s.price*(1+drift+shock)));
      s.hist.push(s.price);
      if(s.hist.length>28) s.hist.shift();
      s.chg=((s.price-s.open)/s.open)*100;
    });
    paint();
  }

  function paint(){
    var box=document.getElementById("marketList");
    if(!box) return;
    ensure();
    var q=((document.getElementById("mktSearch")||{}).value||"").trim().toLowerCase();
    var filt=(window.mktFilter||"all");
    var list=clubs();
    var rows=[];
    for(var i=0;i<list.length;i++){
      var m=list[i], s=st[m.id];
      if(!s) continue;
      if(q && (m.code+" "+(m.league||"")).toLowerCase().indexOf(q)<0) continue;
      if(filt==="gainers" && s.chg<0) continue;
      if(filt==="losers" && s.chg>0) continue;
      rows.push({m:m,s:s});
    }
    rows.sort(function(a,b){ return Math.abs(b.s.chg)-Math.abs(a.s.chg); });
    var html='<div class="mkt-live"><i></i> LIVE · '+rows.length+' clubs · updates every 2s</div>';
    if(!rows.length) html+='<div class="empty">No clubs match</div>';
    for(var r=0;r<rows.length;r++){
      var m=rows[r].m, s=rows[r].s, up=s.chg>=0;
      html+='<div class="mkt-row" onclick="(window.openBuyFromMarket&&openBuyFromMarket('+m.id+'))||(window.goPage&&goPage(\'machines\'))">'+
        '<img class="mkt-badge" src="'+(m.photo||'')+'" alt="" onerror="this.style.visibility=\'hidden\'">'+
        '<div><div class="mkt-name">'+m.code+'</div><div class="mkt-sub">'+(m.league||'')+'</div></div>'+
        '<div class="mkt-spark">'+spark(s.hist,up)+'</div>'+
        '<div><div class="mkt-price">'+fmt(s.price)+'</div><div class="mkt-chg '+(up?"up":"down")+'">'+(up?"+":"")+s.chg.toFixed(2)+'%</div></div>'+
      '</div>';
    }
    box.innerHTML=html;
  }

  function start(){
    ensure();
    paint();
    if(window.__mktTimer) clearInterval(window.__mktTimer);
    window.__mktTimer=setInterval(tick, 2200);
  }

  window.renderMarketList = paint;
  window.startMarketFeed = start;
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", start);
  else start();
  setTimeout(start, 400);
  setTimeout(start, 1200);
})();
