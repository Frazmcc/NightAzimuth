(()=>{
const root=document.querySelector("#contacts");
if(!root||typeof skyXY!=="function"||typeof drawSky!=="function"||typeof renderContacts!=="function")return;

const baseDrawSky=drawSky;
let renderTimer=null;

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

function renderCurrentView(){
  const items=currentViewAircraft();
  if(typeof layers!=="undefined"&&layers.aircraft===false){root.textContent="Aircraft layer is hidden.";return}
  if(!items.length){root.textContent="No aircraft contacts in the current Live Sky view.";return}
  root.replaceChildren(...items.map(contactRow));
}

function queueRender(){
  if(renderTimer!==null)return;
  renderTimer=setTimeout(()=>{renderTimer=null;renderCurrentView()},60);
}

// Keep the contact list tied to the actual viewport, not the wider aircraft
// acquisition set. Panning, zooming, following an object, resizing and layer
// changes all call drawSky, so the list follows the user's view immediately.
drawSky=function(){baseDrawSky();queueRender()};

// Aircraft refreshes still update the backing GeoJSON data, but the visible
// list is rebuilt from skyAircraft using the same skyXY projection as the
// canvas so an entry cannot appear unless that aircraft is actually on screen.
renderContacts=function(data){
  aircraftFeatures=data?.features||[];
  drawSky();
  queueRender();
};

queueRender();
})();
