(()=>{
const AIRCRAFT_RADIUS_MILES=50;
const AIRCRAFT_RADIUS_KM=AIRCRAFT_RADIUS_MILES*1.609344;
const AIRCRAFT_REFRESH_MS=15000;
const AIRCRAFT_CONTINUITY_GRACE_MS=45000;
if(typeof getJson!=="function")return;
const baseGetJson=getJson;
let aircraftRefreshInFlight=false;
let latestAircraftObservedAt=0;
let observerSignature=null;
const aircraftContinuity=new Map();

function contactKey(contact){return String(contact?.icao24||"").trim().toLowerCase()}
function observerKey(params){return `${Number(params?.latitude).toFixed(6)},${Number(params?.longitude).toFixed(6)}`}
function preferredDistanceUnit(){return localStorage.getItem("nightazimuth.distanceUnit")==="km"?"km":"miles"}
function webRadiusLabel(){return preferredDistanceUnit()==="km"?`${Math.round(AIRCRAFT_RADIUS_KM)} km`:`${AIRCRAFT_RADIUS_MILES} mi`}
function withinWebRadius(contact){
  const range=Number(contact?.range_km);
  return !Number.isFinite(range)||range<=AIRCRAFT_RADIUS_KM;
}
function visibleAircraft(contacts){return contacts.filter(contact=>{const elevation=Number(contact?.elevation_deg);return withinWebRadius(contact)&&Number.isFinite(elevation)&&elevation>=0&&elevation<=90})}
function resetContinuityForObserver(params){const next=observerKey(params);if(next!==observerSignature){observerSignature=next;aircraftContinuity.clear();window.nightAzimuthRadarAircraft=[]}}
function reconcileAircraft(incoming,now=Date.now()){
  const seen=new Set();
  for(const contact of incoming){
    if(!withinWebRadius(contact))continue;
    const key=contactKey(contact);
    if(!key)continue;
    seen.add(key);
    aircraftContinuity.set(key,{contact:{...contact,continuity_state:"live",continuity_age_seconds:0},lastSeenMs:now});
  }
  const merged=[];
  for(const [key,entry] of aircraftContinuity){
    const ageMs=Math.max(0,now-entry.lastSeenMs);
    if(ageMs>AIRCRAFT_CONTINUITY_GRACE_MS){aircraftContinuity.delete(key);continue}
    if(seen.has(key)){merged.push(entry.contact);continue}
    merged.push({...entry.contact,position_state:"coasting",continuity_state:"coasting",continuity_age_seconds:Math.round(ageMs/1000)});
  }
  return merged;
}
function enhanceAircraftResponse(data,params){
  resetContinuityForObserver(params);
  const incoming=Array.isArray(data?.aircraft)?data.aircraft:[];
  const all=reconcileAircraft(incoming);
  window.nightAzimuthRadarAircraft=all;
  const visible=visibleAircraft(all);
  const coastingCount=visible.filter(contact=>contact.continuity_state==="coasting").length;
  return{...data,aircraft:visible,count:visible.length,nearby_count:all.length,continuity_coasting_count:coastingCount};
}

// Aircraft rendering is owned exclusively by aircraft-perspective.js. This enhancer
// only constrains and refreshes the aircraft data supplied to that renderer.

// Keep all browser aircraft data within 50 miles of the saved observer. The local
// radar draws from the same bounded acquisition set and can apply a smaller radius.
// Below-horizon contacts are retained only for the optional local radar; Live Sky
// and Live Contacts remain above-horizon-only views.
getJson=async function(path,params={},options={}){
  if(path!=="/api/v1/aircraft")return baseGetJson(path,params,options);
  const request={...params,radius_km:AIRCRAFT_RADIUS_KM,minimum_elevation_deg:-90,include_ground:false};
  const data=await baseGetJson(path,request,options);
  return enhanceAircraftResponse(data,request);
};

async function refreshAircraftFast(){
  if(document.hidden||aircraftRefreshInFlight||!apiBase||!latInput.value||!lonInput.value)return;
  const latitude=latInput.value,longitude=lonInput.value;
  aircraftRefreshInFlight=true;
  try{
    const data=await getJson("/api/v1/aircraft",{latitude,longitude,radius_km:AIRCRAFT_RADIUS_KM,minimum_elevation_deg:-90,include_ground:false},{timeoutMs:20000,retries:0});
    if(latitude!==latInput.value||longitude!==lonInput.value)return;
    const observedAt=Date.parse(data.observed_at||"");
    if(Number.isFinite(observedAt)&&observedAt<latestAircraftObservedAt)return;
    if(Number.isFinite(observedAt))latestAircraftObservedAt=observedAt;
    skyAircraft=data.aircraft||[];
    const nearby=Number(data.nearby_count??window.nightAzimuthRadarAircraft?.length??0);
    const sourceCount=Number(data.source_observation_count??nearby);
    const coasting=Number(data.continuity_coasting_count??0);
    const continuity=coasting?` · ${coasting} coasting`:"";
    setText("#aircraft-count",String(skyAircraft.length));
    setText("#aircraft-detail",`${data.source?.label||"Live aircraft"} · ${skyAircraft.length} above horizon · ${nearby} within ${webRadiusLabel()} · ${sourceCount} source positions${continuity}`);
    setText("#updated",data.observed_at||"Loaded");
    renderContacts(data.geojson||{features:[]});
    drawSky();
  }catch{
    if(skyAircraft.length)setText("#aircraft-detail",`Aircraft refresh delayed · holding ${skyAircraft.length} current contact${skyAircraft.length===1?"":"s"}`);
  }finally{aircraftRefreshInFlight=false}
}

// Run one bounded acquisition immediately so the browser settles on the 50-mile
// dataset even if the initial app.js request was already in flight.
refreshAircraftFast();
setInterval(refreshAircraftFast,AIRCRAFT_REFRESH_MS);
document.addEventListener("visibilitychange",()=>{if(!document.hidden)refreshAircraftFast()});
window.addEventListener("nightazimuth:distance-unit",()=>refreshAircraftFast());
})();
