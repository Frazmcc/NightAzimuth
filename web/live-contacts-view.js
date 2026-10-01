(()=>{
const root=document.querySelector("#contacts");
if(!root||typeof skyXY!=="function"||typeof drawSky!=="function"||typeof renderContacts!=="function")return;

const WEB_AIRCRAFT_RADIUS_KM=50*1.609344;
const KM_PER_NM=1.852;
const M_TO_FT=3.280839895;
const baseDrawSky=drawSky;
const baseShowObject=typeof showObject==="function"?showObject:null;
const baseToggleTracking=typeof toggleTracking==="function"?toggleTracking:null;
const baseUpdateTrackedView=typeof updateTrackedView==="function"?updateTrackedView:null;
const routeCache=new Map();
let renderTimer=null;
let lastRenderSignature=null;

function currentViewAircraft(){
  try{
    if(typeof layers!=="undefined"&&layers.aircraft===false)return[];
    const aircraft=typeof skyAircraft!=="undefined"&&Array.isArray(skyAircraft)?skyAircraft:[];
    const w=innerWidth,h=innerHeight;
    return aircraft.filter(item=>{
      const az=Number(item?.azimuth_deg),el=Number(item?.elevation_deg),range=Number(item?.range_km);
      const withinRadius=!Number.isFinite(range)||range<=WEB_AIRCRAFT_RADIUS_KM;
      return withinRadius&&Number.isFinite(az)&&Number.isFinite(el)&&skyXY(az,el,w,h)!==null;
    });
  }catch{return[]}
}

function formatDistanceNm(rangeKm){
  const km=Number(rangeKm);
  return Number.isFinite(km)?`${(km/KM_PER_NM).toFixed(1)} nm`:null;
}

function formatAltitudeFeet(altitudeM){
  const metres=Number(altitudeM);
  return Number.isFinite(metres)?`${Math.round(metres*M_TO_FT).toLocaleString()} ft`:null;
}

function verticalState(rateMps){
  const rate=Number(rateMps);
  if(!Number.isFinite(rate))return null;
  if(rate>1)return"climbing";
  if(rate<-1)return"descending";
  return"level";
}

function contactRow(aircraft){
  const row=document.createElement("button");
  row.type="button";
  row.className="contact contact-button";
  const selected=trackedObject?.kind==="aircraft"&&trackedObject?.key===aircraft.icao24;
  if(selected)row.classList.add("selected");
  const name=document.createElement("strong");
  const callsign=aircraft.callsign||aircraft.registration||String(aircraft.icao24||"Aircraft").toUpperCase();
  name.textContent=aircraft.operator?`${aircraft.operator} · ${callsign}`:callsign;
  const detail=document.createElement("span");
  const facts=[
    aircraft.display?.make_model||aircraft.type_description||aircraft.type_code||aircraft.display?.role||"Aircraft",
    formatDistanceNm(aircraft.range_km),
    formatAltitudeFeet(aircraft.altitude_m),
    verticalState(aircraft.vertical_rate_mps)
  ].filter(Boolean);
  if(aircraft.military)facts.unshift("Military");
  else if(aircraft.display?.role)facts.unshift(aircraft.display.role);
  detail.textContent=facts.join(" · ");
  row.append(name,detail);
  row.addEventListener("click",()=>focusAircraft(aircraft));
  return row;
}

function renderSignature(items){
  const layerHidden=typeof layers!=="undefined"&&layers.aircraft===false;
  if(layerHidden)return"hidden";
  const view=[Number(facing).toFixed(2),Number(elevationCentre).toFixed(2),Number(fov).toFixed(2),innerWidth,innerHeight].join("|");
  const selected=trackedObject?.kind==="aircraft"?trackedObject.key:"";
  const contacts=items.map(item=>[
    item.icao24||"",
    Number(item.azimuth_deg).toFixed(2),
    Number(item.elevation_deg).toFixed(2),
    Number(item.range_km).toFixed(2),
    Math.round(Number(item.altitude_m)||0),
    Number(item.vertical_rate_mps).toFixed(2),
    item.callsign||item.registration||"",
    item.operator||"",
    item.display?.role||"",
    item.display?.make_model||item.type_description||item.type_code||item.position_state||""
  ].join(":" )).join(";");
  return `${view}|${selected}|${contacts}`;
}

function renderCurrentView(){
  const items=currentViewAircraft();
  const signature=renderSignature(items);
  if(signature===lastRenderSignature)return;
  lastRenderSignature=signature;
  if(typeof layers!=="undefined"&&layers.aircraft===false){root.textContent="Aircraft layer is hidden.";return}
  if(!items.length){root.textContent="No aircraft currently visible in this direction.";return}
  root.replaceChildren(...items.map(contactRow));
}

function queueRender(){
  if(renderTimer!==null)return;
  renderTimer=setTimeout(()=>{renderTimer=null;renderCurrentView()},60);
}

function displayCode(airport){
  if(!airport)return null;
  return airport.iata||airport.icao||airport.display_code||null;
}

function airportPlace(airport){
  if(!airport)return null;
  if(airport.location)return String(airport.location).replace(/,.*$/,"").trim();
  if(!airport.name)return null;
  return String(airport.name)
    .replace(/\s+(International\s+)?Airport$/i,"")
    .replace(/\s+Aerodrome$/i,"")
    .trim();
}

function routeLabel(route){
  const departure=airportPlace(route?.departure);
  const arrival=airportPlace(route?.arrival);
  return departure&&arrival?`${departure} → ${arrival}`:null;
}

async function lookupRoute(callsign){
  const key=String(callsign||"").trim().toUpperCase();
  if(!key)return null;
  if(routeCache.has(key))return Promise.resolve(routeCache.get(key));
  const request=getJson(`/api/v1/aircraft/route/${encodeURIComponent(key)}`,{},{timeoutMs:6000,retries:0})
    .catch(()=>null);
  routeCache.set(key,request);
  const route=await request;
  routeCache.set(key,route);
  return route;
}

function registrationCountry(registration){
  const reg=String(registration||"").trim().toUpperCase();
  if(!reg)return null;
  const prefixes=[
    ["PH-","Netherlands"],["G-","United Kingdom"],["EI-","Ireland"],["D-","Germany"],
    ["F-","France"],["OO-","Belgium"],["HB-","Switzerland"],["OE-","Austria"],
    ["EC-","Spain"],["I-","Italy"],["CS-","Portugal"],["SE-","Sweden"],
    ["LN-","Norway"],["OY-","Denmark"],["OH-","Finland"],["SP-","Poland"],
    ["OK-","Czech Republic"],["OM-","Slovakia"],["HA-","Hungary"],["SX-","Greece"],
    ["TC-","Turkey"],["9H-","Malta"],["LX-","Luxembourg"],["A6-","United Arab Emirates"],
    ["A7-","Qatar"],["HZ-","Saudi Arabia"],["JA","Japan"],["HL","South Korea"],
    ["VH-","Australia"],["ZK-","New Zealand"],["C-","Canada"],["N","United States"]
  ];
  const match=prefixes.find(([prefix])=>reg.startsWith(prefix));
  return match?match[1]:null;
}

function makeDetailRow(label,value){
  if(value===null||value===undefined||value==="")return null;
  const row=document.createElement("div");
  const key=document.createElement("span");
  const val=document.createElement("strong");
  key.textContent=label;
  val.textContent=String(value);
  row.append(key,val);
  return row;
}

function makeSection(title,rows){
  const content=rows.filter(Boolean);
  if(!content.length)return null;
  const section=document.createElement("section");
  const heading=document.createElement("p");
  heading.className="eyebrow";
  heading.textContent=title;
  section.append(heading,...content);
  return section;
}

function yesNo(value){return value?"Yes":"No"}
function selectedAltitude(raw){
  const value=Number(raw.selected_altitude_ft);
  return Number.isFinite(value)?`${Math.round(value).toLocaleString()} ft`:null;
}
function selectedHeading(raw){
  const value=Number(raw.selected_heading_deg);
  return Number.isFinite(value)?`${Math.round(((value%360)+360)%360)}°`:null;
}
function squawkMeaning(raw){
  if(!raw.squawk)return null;
  return raw.squawk_alert?.label||"Normal ATC assigned code";
}

function renderAircraftInspector(raw,routeOverride=null){
  const inspector=document.querySelector("#object-inspector");
  const details=document.querySelector("#inspector-details");
  if(!inspector||!details)return;

  setText("#inspector-type","AIRCRAFT");
  setText("#inspector-name",raw.callsign||raw.registration||raw.icao24||"Aircraft");

  const display=raw.display||{};
  const route=routeOverride||raw.route||{};
  const sections=[
    makeSection("AIRCRAFT",[
      makeDetailRow("Aircraft type / model",display.make_model||raw.type_description||raw.type_code),
      makeDetailRow("Operator / Airline",raw.operator),
      makeDetailRow("Registration",raw.registration),
      makeDetailRow("Callsign",raw.callsign),
      makeDetailRow("Distance",formatDistanceNm(raw.range_km)),
      makeDetailRow("Country of Registration",raw.country||registrationCountry(raw.registration))
    ]),
    makeSection("AUTOPILOT / NAVIGATION",[
      makeDetailRow("Selected altitude",selectedAltitude(raw)),
      makeDetailRow("Selected heading",selectedHeading(raw))
    ]),
    makeSection("TRANSPONDER",[
      makeDetailRow("Squawk",raw.squawk),
      makeDetailRow("Squawk meaning",squawkMeaning(raw)),
      makeDetailRow("Military",yesNo(raw.military)),
      makeDetailRow("PIA",yesNo(raw.pia)),
      makeDetailRow("LADD",yesNo(raw.ladd))
    ]),
    makeSection("FLIGHT",[
      makeDetailRow("Departure",displayCode(route.departure)),
      makeDetailRow("Arrival",displayCode(route.arrival)),
      makeDetailRow("Route",routeLabel(route))
    ])
  ].filter(Boolean);

  details.replaceChildren(...sections);
  inspector.hidden=false;
}

function selectedAircraft(){
  if(trackedObject?.kind!=="aircraft")return null;
  return (Array.isArray(skyAircraft)?skyAircraft:[]).find(item=>item.icao24===trackedObject.key)||null;
}

function renderSelectedWithCachedRoute(aircraft){
  const key=String(aircraft?.callsign||"").trim().toUpperCase();
  const cached=key?routeCache.get(key):null;
  if(cached&&typeof cached.then!=="function")renderAircraftInspector(aircraft,cached);
  else renderAircraftInspector(aircraft);
}

function selectAircraftWithoutRecentering(aircraft){
  if(!aircraft)return;
  trackedObject={kind:"aircraft",key:aircraft.icao24};
  renderSelectedWithCachedRoute(aircraft);
  if(aircraft.callsign){
    lookupRoute(aircraft.callsign).then(route=>{
      if(!route||trackedObject?.kind!=="aircraft"||trackedObject?.key!==aircraft.icao24)return;
      const latest=selectedAircraft()||aircraft;
      renderAircraftInspector(latest,route);
    });
  }
  lastRenderSignature=null;
  drawSky();
  queueRender();
}

focusAircraft=function(aircraft){selectAircraftWithoutRecentering(aircraft)};

if(baseToggleTracking){
  toggleTracking=function(target){
    if(target?.kind!=="aircraft")return baseToggleTracking(target);
    selectAircraftWithoutRecentering(target.item);
    return true;
  };
}

if(baseUpdateTrackedView){
  updateTrackedView=function(){
    if(trackedObject?.kind==="aircraft")return;
    return baseUpdateTrackedView();
  };
}

if(baseShowObject){
  showObject=function(target){
    if(target?.kind==="aircraft"){
      const aircraft=target.item||{};
      selectAircraftWithoutRecentering(aircraft);
      return;
    }
    baseShowObject(target);
  };
}

function markerStyle(){
  return localStorage.getItem("nightazimuth.aircraftMarkerStyle")==="dot"?"dot":"silhouette";
}

function markerSize(rangeKm,selected){
  const range=Number(rangeKm);
  const fraction=Number.isFinite(range)?Math.max(0,Math.min(1,1-range/WEB_AIRCRAFT_RADIUS_KM)):0;
  return 6.5+fraction*7.5+(selected?2:0);
}

function silhouetteKind(aircraft){
  const category=String(aircraft.category||"").toUpperCase();
  const type=String(aircraft.type_code||"").toUpperCase();
  const description=String(aircraft.type_description||aircraft.display?.make_model||"").toLowerCase();
  if(category==="A7"||/helicopter|rotorcraft/.test(description))return"helicopter";
  if(category==="B1"||/glider/.test(description))return"glider";
  if(category==="B6"||/drone|uav/.test(description))return"drone";
  if(category==="A1"||category==="A2"||/cessna|piper|beech|light aircraft/.test(description))return"light";
  if(/^(A3|B7|E1|E2|CRJ)|airbus|boeing|embraer|airliner|jet/.test(type+" "+description))return"jet";
  return"aircraft";
}

function drawSilhouettePath(kind,size){
  const s=size;
  ctx.beginPath();
  if(kind==="helicopter"){
    ctx.ellipse(0,0,s*.25,s*.55,0,0,Math.PI*2);
    ctx.moveTo(-s*.85,0);ctx.lineTo(s*.85,0);
    ctx.moveTo(0,-s*.15);ctx.lineTo(0,-s*.95);
    ctx.moveTo(-s*.28,-s*.78);ctx.lineTo(s*.28,-s*.78);
    return;
  }
  if(kind==="drone"){
    ctx.rect(-s*.18,-s*.18,s*.36,s*.36);
    for(const [x,y] of [[-.55,-.55],[.55,-.55],[-.55,.55],[.55,.55]]){
      ctx.moveTo(Math.sign(x)*s*.18,Math.sign(y)*s*.18);ctx.lineTo(x*s,y*s);
      ctx.moveTo(x*s+s*.18,y*s);ctx.arc(x*s,y*s,s*.18,0,Math.PI*2);
    }
    return;
  }
  const wing=kind==="glider"?1.05:kind==="light"?.72:.9;
  const sweep=kind==="jet"?.1:.28;
  ctx.moveTo(0,-s);
  ctx.lineTo(s*.14,-s*.28);
  ctx.lineTo(s*wing,s*sweep);
  ctx.lineTo(s*wing,s*.28);
  ctx.lineTo(s*.18,s*.1);
  ctx.lineTo(s*.25,s*.72);
  ctx.lineTo(s*.55,s*.88);
  ctx.lineTo(s*.55,s);
  ctx.lineTo(0,s*.82);
  ctx.lineTo(-s*.55,s);
  ctx.lineTo(-s*.55,s*.88);
  ctx.lineTo(-s*.25,s*.72);
  ctx.lineTo(-s*.18,s*.1);
  ctx.lineTo(-s*wing,s*.28);
  ctx.lineTo(-s*wing,s*sweep);
  ctx.lineTo(-s*.14,-s*.28);
  ctx.closePath();
}

function drawAircraftMarker(aircraft,x,y,selected,special){
  const size=markerSize(aircraft.range_km,selected);
  const stroke=selected?"#ffffff":special?"#ffd166":"#8be9ff";
  const glow=selected?"#ffffff":special?"#f59e0b":"#42d9ff";
  ctx.save();
  ctx.translate(x,y);
  const heading=Number(aircraft.track_deg);
  if(Number.isFinite(heading))ctx.rotate((heading-Number(facing))*Math.PI/180);
  ctx.shadowBlur=selected?20:10;
  ctx.shadowColor=glow;
  ctx.strokeStyle=stroke;
  ctx.fillStyle="rgba(3,7,13,.72)";
  ctx.lineWidth=selected?2:1.35;
  if(markerStyle()==="dot"){
    ctx.beginPath();ctx.arc(0,0,selected?6:4,0,Math.PI*2);ctx.fill();ctx.stroke();
  }else{
    drawSilhouettePath(silhouetteKind(aircraft),size);
    ctx.fill();ctx.stroke();
  }
  ctx.restore();
  if(selected){
    ctx.save();ctx.strokeStyle="rgba(255,255,255,.75)";ctx.lineWidth=1.2;
    ctx.beginPath();ctx.arc(x,y,size+7,0,Math.PI*2);ctx.stroke();ctx.restore();
  }
}

drawContacts=function(w,h){
  if(layers.aircraft)for(const aircraft of skyAircraft){
    const az=Number(aircraft.azimuth_deg),el=Number(aircraft.elevation_deg);
    if(!Number.isFinite(az)||!Number.isFinite(el))continue;
    const point=skyXY(az,el,w,h);if(!point)continue;
    const [x,y]=point;
    const special=aircraft.display?.special||aircraft.military||aircraft.squawk_alert;
    const selected=trackedObject?.kind==="aircraft"&&trackedObject.key===aircraft.icao24;
    drawAircraftMarker(aircraft,x,y,selected,special);
    ctx.fillStyle=selected?"#ffffff":"#dff8ff";
    ctx.textAlign="left";ctx.font=selected?"bold 10px ui-monospace,monospace":"10px ui-monospace,monospace";
    if(labels.aircraft)ctx.fillText((aircraft.display?.role?`${aircraft.display.role} · `:"")+(aircraft.callsign||aircraft.registration||aircraft.icao24||"AIR"),x+12,y-8);
    hit("aircraft",aircraft,[x,y],Math.max(14,markerSize(aircraft.range_km,selected)+7));
  }
  if(layers.satellites)for(const satellite of skySatellites){
    const az=Number(satellite.azimuth_deg),el=Number(satellite.elevation_deg);
    if(!Number.isFinite(az)||!Number.isFinite(el))continue;
    const point=skyXY(az,el,w,h);if(!point)continue;
    const [x,y]=point;ctx.strokeStyle="#ffd76a";ctx.fillStyle="#ffd76a";
    ctx.beginPath();ctx.moveTo(x,y-5);ctx.lineTo(x+5,y);ctx.lineTo(x,y+5);ctx.lineTo(x-5,y);ctx.closePath();ctx.stroke();
    ctx.font="10px ui-monospace,monospace";ctx.textAlign="left";
    if(labels.satellites)ctx.fillText(satellite.name||"SAT",x+8,y-7);
    hit("satellite",satellite,[x,y],12);
  }
};

const markerSelect=document.querySelector("#aircraft-marker-style");
if(markerSelect){
  markerSelect.value=markerStyle();
  markerSelect.addEventListener("change",()=>{
    const value=markerSelect.value==="dot"?"dot":"silhouette";
    localStorage.setItem("nightazimuth.aircraftMarkerStyle",value);
    drawSky();
  });
}

// Keep the contact list tied to the actual viewport, not the wider aircraft acquisition set.
drawSky=function(){baseDrawSky();queueRender()};

renderContacts=function(data){
  aircraftFeatures=data?.features||[];
  lastRenderSignature=null;
  const selected=selectedAircraft();
  if(selected)renderSelectedWithCachedRoute(selected);
  drawSky();
  queueRender();
};

queueRender();
})();