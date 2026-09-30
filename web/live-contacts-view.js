(()=>{
const root=document.querySelector("#contacts");
if(!root||typeof skyXY!=="function"||typeof drawSky!=="function"||typeof renderContacts!=="function")return;

const baseDrawSky=drawSky;
const baseShowObject=typeof showObject==="function"?showObject:null;
const routeCache=new Map();
let renderTimer=null;
let lastRenderSignature=null;

function currentViewAircraft(){
  try{
    if(typeof layers!=="undefined"&&layers.aircraft===false)return[];
    const aircraft=typeof skyAircraft!=="undefined"&&Array.isArray(skyAircraft)?skyAircraft:[];
    const w=innerWidth,h=innerHeight;
    return aircraft.filter(item=>{
      const az=Number(item?.azimuth_deg),el=Number(item?.elevation_deg);
      return Number.isFinite(az)&&Number.isFinite(el)&&skyXY(az,el,w,h)!==null;
    });
  }catch{return[]}
}

function contactRow(aircraft){
  const row=document.createElement("button");
  row.type="button";
  row.className="contact contact-button";
  const name=document.createElement("strong");
  name.textContent=(aircraft.display?.role?aircraft.display.role+" · ":"")+(aircraft.callsign||aircraft.registration||aircraft.icao24||"Unknown");
  const detail=document.createElement("span");
  const role=aircraft.display?.role||"Aircraft";
  detail.textContent=`${role} · ${Math.round(aircraft.altitude_m||0)} m · ${aircraft.display?.make_model||aircraft.type_description||aircraft.type_code||aircraft.position_state||"unknown"}`;
  row.append(name,detail);
  row.addEventListener("click",()=>focusAircraft(aircraft));
  return row;
}

function renderSignature(items){
  const layerHidden=typeof layers!=="undefined"&&layers.aircraft===false;
  if(layerHidden)return"hidden";
  const view=[Number(facing).toFixed(2),Number(elevationCentre).toFixed(2),Number(fov).toFixed(2),innerWidth,innerHeight].join("|");
  const contacts=items.map(item=>[
    item.icao24||"",
    Number(item.azimuth_deg).toFixed(2),
    Number(item.elevation_deg).toFixed(2),
    Math.round(Number(item.altitude_m)||0),
    item.callsign||item.registration||"",
    item.display?.role||"",
    item.display?.make_model||item.type_description||item.type_code||item.position_state||""
  ].join(":" )).join(";");
  return `${view}|${contacts}`;
}

function renderCurrentView(){
  const items=currentViewAircraft();
  const signature=renderSignature(items);
  if(signature===lastRenderSignature)return;
  lastRenderSignature=signature;
  if(typeof layers!=="undefined"&&layers.aircraft===false){root.textContent="Aircraft layer is hidden.";return}
  if(!items.length){root.textContent="No aircraft contacts in the current Live Sky view.";return}
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
  if(routeCache.has(key))return routeCache.get(key);
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

function aircraftClass(raw){
  if(raw.military)return"Military aircraft";
  const category=String(raw.category||"").toUpperCase();
  const type=String(raw.type_code||"").toUpperCase();
  const description=String(raw.type_description||raw.display?.make_model||"").toLowerCase();

  if(category==="A7"||/helicopter|rotorcraft/.test(description))return"Helicopter";
  if(category==="B1")return"Glider";
  if(category==="B2")return"Balloon / airship";
  if(category==="B3")return"Parachutist / skydiver";
  if(category==="B4")return"Ultralight aircraft";
  if(category==="B6")return"UAV / drone";
  if(category==="B7")return"Space / trans-atmospheric vehicle";

  if(/gulfstream|learjet|citation|falcon|challenger|phenom|hawker|global express|business jet/.test(description))return"Business jet";
  if(/^(E17[05]|E19[05]|E2\d\d|CRJ\d|A3\d\d|A2[01]N|B7\d\d|B3[789]M)$/.test(type)||/airbus|boeing|embraer e-?1|embraer e-?2|regional jet|airliner/.test(description))return"Passenger jet";
  if(category==="A1")return"Light aircraft";
  if(category==="A2")return/jet/.test(description)?"Small jet":"Small aircraft";
  if(category==="A6")return"High-performance aircraft";
  if(["A3","A4","A5"].includes(category))return"Large aircraft";
  return null;
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

function yesNo(value){return value===null||value===undefined?null:(value?"Yes":"No")}

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
      makeDetailRow("Aircraft class",aircraftClass(raw)),
      makeDetailRow("ICAO aircraft type",raw.type_code),
      makeDetailRow("Registration",raw.registration),
      makeDetailRow("Callsign",raw.callsign),
      makeDetailRow("ICAO24 / Hex",raw.icao24?String(raw.icao24).toUpperCase():null),
      makeDetailRow("Operator / airline",raw.operator),
      makeDetailRow("Country",raw.country||registrationCountry(raw.registration)),
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

if(baseShowObject){
  window.showObject=function(target){
    if(target?.kind==="aircraft"){
      const aircraft=target.item||{};
      renderAircraftInspector(aircraft);
      if(!aircraft.route&&aircraft.callsign){
        lookupRoute(aircraft.callsign).then(route=>{
          if(!route)return;
          const stillSelected=typeof trackedObject==="undefined"||
            (trackedObject?.kind==="aircraft"&&trackedObject?.key===aircraft.icao24);
          if(stillSelected)renderAircraftInspector(aircraft,route);
        });
      }
      return;
    }
    baseShowObject(target);
  };
}

// Keep the contact list tied to the actual viewport, not the wider aircraft
// acquisition set. The signature prevents satellite-only redraws from rebuilding
// the contacts DOM several times per second when neither view nor aircraft changed.
drawSky=function(){baseDrawSky();queueRender()};

renderContacts=function(data){
  aircraftFeatures=data?.features||[];
  lastRenderSignature=null;
  drawSky();
  queueRender();
};

queueRender();
})();
