(()=>{
const AIRCRAFT_RADIUS_KM=400;
const AIRCRAFT_REFRESH_MS=15000;
if(typeof getJson!=="function")return;
const baseGetJson=getJson;
let aircraftRefreshInFlight=false;
let latestAircraftObservedAt=0;

function visibleAircraft(contacts){return contacts.filter(contact=>{const elevation=Number(contact?.elevation_deg);return Number.isFinite(elevation)&&elevation>=0&&elevation<=90})}
function enhanceAircraftResponse(data){const all=Array.isArray(data?.aircraft)?data.aircraft:[];window.nightAzimuthRadarAircraft=all;const visible=visibleAircraft(all);return{...data,aircraft:visible,count:visible.length,nearby_count:all.length}}

// Fetch a wider area and keep below-horizon contacts for the local radar, while
// preserving Live Contacts / Live Sky as above-horizon-only views.
getJson=async function(path,params={},options={}){if(path!=="/api/v1/aircraft")return baseGetJson(path,params,options);const data=await baseGetJson(path,{...params,radius_km:AIRCRAFT_RADIUS_KM,minimum_elevation_deg:-90,include_ground:false},options);return enhanceAircraftResponse(data)};

async function refreshAircraftFast(){
  if(aircraftRefreshInFlight||!apiBase||!latInput.value||!lonInput.value)return;
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
    setText("#aircraft-count",String(skyAircraft.length));
    setText("#aircraft-detail",`${data.source?.label||"Live aircraft"} · ${skyAircraft.length} above horizon · ${nearby} nearby · ${sourceCount} source positions`);
    setText("#updated",data.observed_at||"Loaded");
    renderContacts(data.geojson||{features:[]});
    drawSky();
  }catch{
    if(skyAircraft.length)setText("#aircraft-detail",`Aircraft refresh delayed · showing ${skyAircraft.length} last-known above-horizon contact${skyAircraft.length===1?"":"s"}`);
  }finally{aircraftRefreshInFlight=false}
}

refreshAircraftFast();
setInterval(refreshAircraftFast,AIRCRAFT_REFRESH_MS);
})();
