/* Own Club live market — Solara-style list + home cards */
(function(){
  var CLUBS = [
    {id:1,code:"Manchester City",league:"Premier League",mv:5.0e9,photo:"https://crests.football-data.org/65.png"},
    {id:2,code:"Arsenal",league:"Premier League",mv:3.5e9,photo:"https://crests.football-data.org/57.png"},
    {id:3,code:"Liverpool",league:"Premier League",mv:5.3e9,photo:"https://crests.football-data.org/64.png"},
    {id:4,code:"Chelsea",league:"Premier League",mv:3.1e9,photo:"https://crests.football-data.org/61.png"},
    {id:5,code:"Manchester United",league:"Premier League",mv:6.0e9,photo:"https://crests.football-data.org/66.png"},
    {id:6,code:"Tottenham",league:"Premier League",mv:2.8e9,photo:"https://crests.football-data.org/73.png"},
    {id:7,code:"Real Madrid",league:"La Liga",mv:6.6e9,photo:"https://crests.football-data.org/86.png"},
    {id:8,code:"Barcelona",league:"La Liga",mv:5.5e9,photo:"https://crests.football-data.org/81.png"},
    {id:9,code:"Atletico Madrid",league:"La Liga",mv:1.6e9,photo:"https://crests.football-data.org/78.png"},
    {id:10,code:"Athletic Club",league:"La Liga",mv:0.9e9,photo:"https://crests.football-data.org/77.png"},
    {id:11,code:"Real Sociedad",league:"La Liga",mv:0.55e9,photo:"https://crests.football-data.org/92.png"},
    {id:12,code:"Villarreal",league:"La Liga",mv:0.42e9,photo:"https://crests.football-data.org/94.png"},
    {id:13,code:"Juventus",league:"Serie A",mv:2.0e9,photo:"https://crests.football-data.org/109.png"},
    {id:14,code:"Inter Milan",league:"Serie A",mv:1.3e9,photo:"https://crests.football-data.org/108.png"},
    {id:15,code:"AC Milan",league:"Serie A",mv:1.4e9,photo:"https://crests.football-data.org/98.png"},
    {id:16,code:"Napoli",league:"Serie A",mv:0.85e9,photo:"https://crests.football-data.org/113.png"},
    {id:17,code:"PSG",league:"Ligue 1",mv:4.4e9,photo:"https://crests.football-data.org/524.png"},
    {id:18,code:"Marseille",league:"Ligue 1",mv:0.48e9,photo:"https://crests.football-data.org/516.png"},
    {id:19,code:"Bayern Munich",league:"Bundesliga",mv:5.1e9,photo:"https://crests.football-data.org/5.png"},
    {id:20,code:"Borussia Dortmund",league:"Bundesliga",mv:2.0e9,photo:"https://crests.football-data.org/4.png"},
    {id:21,code:"Al Hilal",league:"Saudi Pro League",mv:0.90e9,photo:"https://crests.football-data.org/65.png"},
    {id:22,code:"Al Nassr",league:"Saudi Pro League",mv:0.75e9,photo:"https://crests.football-data.org/66.png"},
    {id:23,code:"Al Ittihad",league:"Saudi Pro League",mv:0.55e9,photo:"https://crests.football-data.org/61.png"},
    {id:24,code:"Al Ahli",league:"Saudi Pro League",mv:0.50e9,photo:"https://crests.football-data.org/57.png"},
    {id:25,code:"Inter Miami",league:"MLS",mv:1.1e9,photo:"https://crests.football-data.org/81.png"},
    {id:26,code:"LAFC",league:"MLS",mv:1.0e9,photo:"https://crests.football-data.org/86.png"},
    {id:27,code:"LA Galaxy",league:"MLS",mv:0.60e9,photo:"https://crests.football-data.org/73.png"},
    {id:28,code:"Atlanta United",league:"MLS",mv:0.70e9,photo:"https://crests.football-data.org/64.png"},
    {id:29,code:"Leicester City",league:"Championship",mv:0.45e9,photo:"https://crests.football-data.org/338.png"},
    {id:30,code:"Leeds United",league:"Championship",mv:0.40e9,photo:"https://crests.football-data.org/341.png"},
    {id:31,code:"Southampton",league:"Championship",mv:0.38e9,photo:"https://crests.football-data.org/340.png"},
    {id:32,code:"Ipswich Town",league:"Championship",mv:0.25e9,photo:"https://crests.football-data.org/349.png"}
  ];
  function fmt(n){
    if(n>=1e9) return "$"+(n/1e9).toFixed(2)+"B";
    if(n>=1e6) return "$"+(n/1e6).toFixed(2)+"M";
    return "$"+n.toFixed(0);
  }
  var st = {};
  function seed(){
    for(var i=0;i<CLUBS.length;i++){
      var c=CLUBS[i];
      if(st[c.id]) continue;
      var hist=[], p=c.mv;
      for(var h=0;h<24;h++){ p=p*(1+(Math.random()-0.48)*0.012); hist.push(p); }
      st[c.id]={price:p,open:c.mv,base:c.mv,hist:hist,chg:((p-c.mv)/c.mv)*100};
    }
  }
  function spark(hist,up){
    if(!hist||hist.length<2) return "";
    var min=Math.min.apply(null,hist), max=Math.max.apply(null,hist), range=(max-min)||1;
    var w=78,h=32,pad=2,pts=[];
    for(var i=0;i<hist.length;i++){
      pts.push((pad+(i/(hist.length-1))*(w-pad*2)).toFixed(1)+","+(h-pad-((hist[i]-min)/range)*(h-pad*2)).toFixed(1));
    }
    return '<svg viewBox="0 0 '+w+' '+h+'" preserveAspectRatio="none"><polyline fill="none" stroke="'+(up?"#2ee56a":"#ff5b5b")+'" stroke-width="1.8" stroke-linejoin="round" points="'+pts.join(" ")+'"/></svg>';
  }
  function paint(){
    var box=document.getElementById("marketList");
    if(!box) return;
    seed();
    var q=((document.getElementById("mktSearch")||{}).value||"").trim().toLowerCase();
    var filt=window.mktFilter||"all";
    var rows=[];
    for(var i=0;i<CLUBS.length;i++){
      var c=CLUBS[i], s=st[c.id];
      if(q && (c.code+" "+c.league).toLowerCase().indexOf(q)<0) continue;
      if(filt==="gainers" && s.chg<0) continue;
      if(filt==="losers" && s.chg>0) continue;
      rows.push({c:c,s:s});
    }
    rows.sort(function(a,b){ return Math.abs(b.s.chg)-Math.abs(a.s.chg); });
    var html='<div class="mkt-live">LIVE · '+rows.length+' clubs · updates every 2s</div>';
    for(var r=0;r<rows.length;r++){
      var c=rows[r].c, s=rows[r].s, up=s.chg>=0;
      html+='<div class="mkt-row" onclick="(window.openBuyFromMarket&&openBuyFromMarket('+c.id+'))">'+
        '<img class="mkt-badge" src="'+c.photo+'" alt="">'+
        '<div><div class="mkt-name">'+c.code+'</div><div class="mkt-sub">'+c.league+'</div></div>'+
        '<div class="mkt-spark">'+spark(s.hist,up)+'</div>'+
        '<div><div class="mkt-price">'+fmt(s.price)+'</div><div class="mkt-chg '+(up?"up":"down")+'">'+(up?"+":"")+s.chg.toFixed(2)+'%</div></div></div>';
    }
    box.innerHTML=html;
  }
  function paintHome(){
    var home=document.getElementById("home");
    if(!home) return;
    var box=document.getElementById("homeMarkets");
    if(!box){
      box=document.createElement("div");
      box.id="homeMarkets";
      home.appendChild(box);
    }
    seed();
    var picks=CLUBS.slice(0,8);
    var html='<div style="display:flex;justify-content:space-between;align-items:center;margin:10px 0 8px"><h3 style="margin:0;color:#fff;font-size:18px">Markets</h3><button type="button" onclick="window.goPage&&goPage(\'market\')" style="background:none;border:0;color:#2ee56a;font-weight:700">View All →</button></div><div class="mkt-cards">';
    for(var i=0;i<picks.length;i++){
      var c=picks[i], s=st[c.id], up=s.chg>=0;
      html+='<div class="mkt-card" onclick="(window.openBuyFromMarket&&openBuyFromMarket('+c.id+'))">'+
        '<div class="nm">'+c.code+'</div><div class="mkt-sub">'+c.league+'</div>'+
        '<div class="mkt-spark">'+spark(s.hist,up)+'</div>'+
        '<div class="px">'+fmt(s.price)+'</div><div class="mkt-chg '+(up?"up":"down")+'">'+(up?"+":"")+s.chg.toFixed(2)+'%</div></div>';
    }
    html+='</div>';
    box.innerHTML=html;
  }
  function tick(){
    seed();
    Object.keys(st).forEach(function(id){
      var s=st[id];
      var drift=(s.base-s.price)/s.base*0.08;
      var shock=(Math.random()-0.5)*0.018;
      s.price=Math.max(s.base*0.82, Math.min(s.base*1.22, s.price*(1+drift+shock)));
      s.hist.push(s.price); if(s.hist.length>28) s.hist.shift();
      s.chg=((s.price-s.open)/s.open)*100;
    });
    paint();
    try{paintHome();}catch(e){}
  }
  function start(){
    seed(); paint(); try{paintHome();}catch(e){}
    if(window.__ocMkt) clearInterval(window.__ocMkt);
    window.__ocMkt=setInterval(tick, 2000);
  }
  window.renderMarketList=paint;
  window.startMarketFeed=start;
  window.CLUB_MARKET_SEED=CLUBS;
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded", start);
  else start();
  setTimeout(start, 400);
  setTimeout(start, 1500);
})();
