(()=>{
const root=document.querySelector("#contacts");
if(!root||typeof skyXY!=="function"||typeof drawSky!=="function"||typeof renderContacts!=="function")return;

const baseDrawSky=drawSky;
const baseShowObject=typeof showObject==="function"?showObject:null;
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

function finiteNumber(value){
  const number=Number(value);
  return Number.isFinite(number)?number:null;
}

function formatNumber(value,digits=0){
  const number=finiteNumber(value);
  if(number===null)return null;
  return number.toLocaleString(undefined,{minimumFractionDigits:digits,maximumFractionDigits:digits});
}

function formatDegrees(value,digits=1){
  const number=formatNumber(value,digits);
  return number===null?null:`${number}°`;
}

function formatAltitude(value){
  const metres=finiteNumber(value);
  if(metres===null)return null;
  const feet=metres*3.280839895;
  return `${formatNumber(feet,0)} ft (${formatNumber(metres,0)} m)`;
}

function formatGroundSpeed(value){
  const mps=finiteNumber(value);
  if(mps===null)return null;
  const knots=mps/0.514444;
  const kmh=mps*3.6;
  return `${formatNumber(knots,0)} kt (${formatNumber(kmh,0)} km/h)`;
}

function formatVerticalRate(value){
  const mps=finiteNumber(value);
  if(mps===null)return null;
  const fpm=mps/0.00508;
  const sign=fpm>0?"+":"";
  return `${sign}${formatNumber(fpm,0)} ft/min (${mps>0?"+":""}${formatNumber(mps,1)} m/s)`;
}

function formatAge(value){
  const seconds=finiteNumber(value);
  return seconds===null?null:`${formatNumber(seconds,1)} s`;
}

function displayCode(airport){
  if(!airport)return null;
  return airport.display_code||airport.iata||airport.icao||null;
}

function formatAirport(airport){
  if(!airport)return null;
  const code=displayCode(airport);
  const name=airport.name||null;
  if(name&&code)return `${name} (${code})`;
  return name||code;
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

function renderAircraftInspector(raw){
  const inspector=document.querySelector("#object-inspector");
  const details=document.querySelector("#inspector-details");
  if(!inspector||!details)return;

  setText("#inspector-type","AIRCRAFT");
  setText("#inspector-name",raw.callsign||raw.registration||raw.icao24||"Aircraft");

  const display=raw.display||{};
  const route=raw.route||{};
  const sections=[
    makeSection("AIRCRAFT",[
      makeDetailRow("Aircraft type / model",display.make_model||raw.type_description||raw.type_code),
      makeDetailRow("Capacity",display.capacity),
      makeDetailRow("ICAO aircraft type",raw.type_code),
      makeDetailRow("Registration",raw.registration),
      makeDetailRow("Callsign",raw.callsign),
      makeDetailRow("ICAO24 / Hex",raw.icao24?String(raw.icao24).toUpperCase():null),
      makeDetailRow("Operator",raw.operator),
      makeDetailRow("Role",display.role),
      makeDetailRow("Military",raw.military==null?null:(raw.military?"Yes":"No"))
    ]),
    makeSection("FLIGHT",[
      makeDetailRow("Departure",formatAirport(route.departure)),
      makeDetailRow("Arrival",formatAirport(route.arrival))
    ]),
    makeSection("POSITION",[
      makeDetailRow("Azimuth",formatDegrees(raw.azimuth_deg,2)),
      makeDetailRow("Elevation",formatDegrees(raw.elevation_deg,2)),
      makeDetailRow("Position state",raw.position_state),
      makeDetailRow("Position age",formatAge(raw.position_age_seconds))
    ]),
    makeSection("ALTITUDE & SPEED",[
      makeDetailRow("Altitude",formatAltitude(raw.altitude_m)),
      makeDetailRow("Ground speed",formatGroundSpeed(raw.ground_speed_mps)),
      makeDetailRow("Track",formatDegrees(raw.track_deg,1)),
      makeDetailRow("Vertical rate",formatVerticalRate(raw.vertical_rate_mps))
    ]),
    makeSection("TRANSPONDER",[
      makeDetailRow("Squawk / meaning",display.squawk||raw.squawk),
      display.squawk&&raw.squawk&&String(display.squawk)!==String(raw.squawk)?makeDetailRow("Squawk",raw.squawk):null
    ]),
    makeSection("ADS-B / TRACKING",[
      makeDetailRow("Data source",raw.source_label),
      makeDetailRow("Source ID",raw.source_id)
    ])
  ].filter(Boolean);

  details.replaceChildren(...sections);
  inspector.hidden=false;
}

if(baseShowObject){
  window.showObject=function(target){
    if(target?.kind==="aircraft"){
      renderAircraftInspector(target.item||{});
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
