// Tesla Roadster / Starman deep-space marker and Live Contacts detail.
// The object arrives inside /api/v1/sky but is kept separate from Hipparcos stars
// so it never contaminates camera plate-solving/catalogue logic.
(function(){
  if(typeof drawCelestial!=="function"||typeof skyXY!=="function")return;
  const skyCanvas=document.querySelector("#sky-canvas");
  if(!skyCanvas)return;

  const ROADSTER_ID="tesla-roadster-starman";
  const ROADSTER_RED="#d72b35";
  const MEDIA_URL="https://upload.wikimedia.org/wikipedia/commons/1/17/Elon_Musk%27s_Tesla_Roadster_%2840110298232%29.jpg";
  const MEDIA_SOURCE="https://commons.wikimedia.org/wiki/File:Elon_Musk%27s_Tesla_Roadster_(40110298232).jpg";
  let roadsterHits=[];
  let panelActive=false;
  let panelSignature="";

  const contactsPanel=document.querySelector(".contacts-panel");
  const contactsTitle=contactsPanel?.querySelector(".section-head h2")||null;
  const contactsRoot=document.querySelector("#contacts");
  const aircraftDetail=document.querySelector("#aircraft-detail");
  const contactsBody=document.querySelector("#contacts-body");
  const defaultContactsTitle=contactsTitle?.textContent||"Aircraft";
  let roadsterDetail=document.querySelector("#roadster-contact-detail");
  if(!roadsterDetail&&contactsBody){
    roadsterDetail=document.createElement("div");
    roadsterDetail.id="roadster-contact-detail";
    roadsterDetail.className="contacts roadster-contact-detail";
    roadsterDetail.hidden=true;
    contactsBody.insertBefore(roadsterDetail,contactsRoot||null);
  }

  const finite=value=>{const number=Number(value);return Number.isFinite(number)?number:null};
  const roadsters=()=>Array.isArray(celestialSky?.deep_space_objects)?celestialSky.deep_space_objects:[];
  const roadsterKey=item=>item?.id||item?.jpl_target_id||ROADSTER_ID;
  const isSelected=item=>typeof trackedObject!=="undefined"&&trackedObject?.kind==="deep_space"&&trackedObject.key===roadsterKey(item);

  function makeDetailRow(label,value){
    if(value===null||value===undefined||value==="")return null;
    const row=document.createElement("div"),key=document.createElement("span"),data=document.createElement("strong");
    row.className="contact";key.textContent=label;data.textContent=String(value);row.append(key,data);return row;
  }

  function makeSection(title,rows){
    const content=rows.filter(Boolean);if(!content.length)return null;
    const section=document.createElement("section"),heading=document.createElement("p");
    heading.className="eyebrow";heading.textContent=title;section.append(heading,...content);return section;
  }

  function formatNumber(value,digits=2){
    const number=finite(value);return number===null?null:number.toFixed(digits);
  }

  function formatAu(value){
    const number=finite(value);return number===null?null:`${number.toFixed(4)} AU`;
  }

  function formatEarthDistance(item){
    const km=finite(item?.distance_earth_km),au=finite(item?.distance_earth_au);
    if(km===null&&au===null)return null;
    if(km===null)return `${au.toFixed(4)} AU`;
    const million=km/1_000_000;
    return au===null?`${million.toFixed(1)} million km`:`${million.toFixed(1)} million km · ${au.toFixed(4)} AU`;
  }

  function formatRate(value){
    const number=finite(value);if(number===null)return null;
    const direction=number>0?"away from Earth":number<0?"toward Earth":"no radial change";
    return `${Math.abs(number).toFixed(2)} km/s · ${direction}`;
  }

  function formatDate(value){
    if(!value)return null;const date=new Date(value);
    return Number.isNaN(date.getTime())?String(value):date.toLocaleString();
  }

  function restoreRoadsterContacts(clearTracking=false){
    panelActive=false;panelSignature="";
    if(clearTracking&&typeof trackedObject!=="undefined"&&trackedObject?.kind==="deep_space")trackedObject=null;
    if(roadsterDetail)roadsterDetail.hidden=true;
    if(contactsTitle)contactsTitle.textContent=defaultContactsTitle;
    if(contactsRoot)contactsRoot.hidden=false;
    if(aircraftDetail)aircraftDetail.hidden=false;
  }

  function renderMedia(){
    const figure=document.createElement("figure");figure.className="roadster-media";
    const image=document.createElement("img");
    image.src=MEDIA_URL;image.alt="Historical SpaceX onboard view from the Tesla Roadster with Earth visible";
    image.loading="lazy";image.decoding="async";image.referrerPolicy="no-referrer";
    const caption=document.createElement("figcaption");
    caption.textContent="Historical SpaceX onboard view · 6 Feb 2018 · CC0/public domain · not live";
    const source=document.createElement("a");source.href=MEDIA_SOURCE;source.target="_blank";source.rel="noopener noreferrer";source.textContent="Source";
    caption.append(" · ",source);figure.append(image,caption);return figure;
  }

  function renderRoadsterContacts(item){
    if(!roadsterDetail||!item)return;
    const signature=[item.ephemeris_at,item.azimuth_deg,item.elevation_deg,item.distance_earth_au,item.distance_sun_au].join("|");
    if(panelActive&&signature===panelSignature)return;
    panelActive=true;panelSignature=signature;
    if(contactsTitle)contactsTitle.textContent="Deep Space";
    if(contactsRoot)contactsRoot.hidden=true;
    if(aircraftDetail)aircraftDetail.hidden=true;
    const satelliteDetail=document.querySelector("#satellite-contact-detail");if(satelliteDetail)satelliteDetail.hidden=true;
    const genericInspector=document.querySelector("#object-inspector");if(genericInspector)genericInspector.hidden=true;
    roadsterDetail.hidden=false;

    const status=document.createElement("p");status.className="muted roadster-status";
    status.textContent="● TESLA ROADSTER / STARMAN · JPL PREDICTED EPHEMERIS";
    const sections=[
      makeSection("IDENTIFICATION",[
        makeDetailRow("Name",item.name),
        makeDetailRow("Object class",item.object_type),
        makeDetailRow("International designator",item.international_designator),
        makeDetailRow("JPL Horizons target",item.jpl_target_id),
        makeDetailRow("Launch date",item.launch_date),
        makeDetailRow("Launch vehicle",item.launch_vehicle),
        makeDetailRow("Payload",item.payload),
        makeDetailRow("Body colour",item.body_colour),
        makeDetailRow("Tracking",item.tracking_mode)
      ]),
      makeSection("SKY POSITION",[
        makeDetailRow("Azimuth",formatNumber(item.azimuth_deg)==null?null:`${formatNumber(item.azimuth_deg)}°`),
        makeDetailRow("Elevation",formatNumber(item.elevation_deg)==null?null:`${formatNumber(item.elevation_deg)}°`),
        makeDetailRow("Right ascension",formatNumber(item.right_ascension_deg,4)==null?null:`${formatNumber(item.right_ascension_deg,4)}°`),
        makeDetailRow("Declination",formatNumber(item.declination_deg,4)==null?null:`${formatNumber(item.declination_deg,4)}°`),
        makeDetailRow("Constellation",item.constellation),
        makeDetailRow("Above horizon",finite(item.elevation_deg)!==null&&Number(item.elevation_deg)>=0?"Yes":"No")
      ]),
      makeSection("DISTANCE & MOTION",[
        makeDetailRow("Distance from Earth",formatEarthDistance(item)),
        makeDetailRow("Distance from Sun",formatAu(item.distance_sun_au)),
        makeDetailRow("Earth range rate",formatRate(item.earth_range_rate_km_s)),
        makeDetailRow("Heliocentric speed",finite(item.heliocentric_speed_km_s)==null?null:`${Number(item.heliocentric_speed_km_s).toFixed(2)} km/s`),
        makeDetailRow("Observer-relative speed",finite(item.observer_relative_speed_km_s)==null?null:`${Number(item.observer_relative_speed_km_s).toFixed(2)} km/s`),
        makeDetailRow("One-way light time",finite(item.light_time_minutes)==null?null:`${Number(item.light_time_minutes).toFixed(2)} min`)
      ]),
      makeSection("GEOMETRY",[
        makeDetailRow("Solar elongation",finite(item.solar_elongation_deg)==null?null:`${Number(item.solar_elongation_deg).toFixed(2)}°`),
        makeDetailRow("Phase angle",finite(item.phase_angle_deg)==null?null:`${Number(item.phase_angle_deg).toFixed(2)}°`),
        makeDetailRow("Heliocentric ecliptic longitude",finite(item.heliocentric_ecliptic_longitude_deg)==null?null:`${Number(item.heliocentric_ecliptic_longitude_deg).toFixed(2)}°`),
        makeDetailRow("Heliocentric ecliptic latitude",finite(item.heliocentric_ecliptic_latitude_deg)==null?null:`${Number(item.heliocentric_ecliptic_latitude_deg).toFixed(2)}°`),
        makeDetailRow("Apparent magnitude",finite(item.apparent_magnitude)==null?"Not supplied by Horizons":Number(item.apparent_magnitude).toFixed(2))
      ]),
      makeSection("EPHEMERIS",[
        makeDetailRow("Ephemeris time",formatDate(item.ephemeris_at)),
        makeDetailRow("Data source",item.data_source),
        makeDetailRow("Interpretation","Calculated trajectory position — no live telemetry is received from the Roadster")
      ])
    ].filter(Boolean);
    const back=document.createElement("button");back.type="button";back.textContent="Back to aircraft";back.addEventListener("click",()=>{restoreRoadsterContacts(true);drawSky()});
    roadsterDetail.replaceChildren(status,...sections,renderMedia(),back);
  }

  function selectRoadster(item,toggle=true){
    if(!item)return false;
    const key=roadsterKey(item),already=isSelected(item);
    if(toggle&&already){restoreRoadsterContacts(true);drawSky();return false}
    trackedObject={kind:"deep_space",key};renderRoadsterContacts(item);drawSky();return true;
  }

  function drawRoadster(w,h){
    roadsterHits=[];
    if(typeof layers!=="undefined"&&layers.stars===false)return;
    for(const item of roadsters()){
      const az=finite(item.azimuth_deg),el=finite(item.elevation_deg);if(az===null||el===null)continue;
      const point=skyXY(az,el,w,h);if(!point)continue;
      const selected=isSelected(item),x=point[0],y=point[1],radius=selected?4.2:2.8;
      ctx.save();ctx.fillStyle=ROADSTER_RED;ctx.shadowColor=ROADSTER_RED;ctx.shadowBlur=selected?14:6;
      ctx.beginPath();ctx.arc(x,y,radius,0,Math.PI*2);ctx.fill();ctx.shadowBlur=0;
      if(selected){ctx.strokeStyle="#ffffff";ctx.lineWidth=1;ctx.beginPath();ctx.arc(x,y,9,0,Math.PI*2);ctx.stroke()}
      if((typeof labels!=="undefined"&&labels.stars)||selected){ctx.fillStyle=selected?"#ffffff":"#ff8790";ctx.font=selected?"bold 10px ui-monospace,monospace":"10px ui-monospace,monospace";ctx.fillText("TESLA ROADSTER",x+8,y-7)}
      ctx.restore();roadsterHits.push({item,x,y,r:12});
      if(selected)renderRoadsterContacts(item);
    }
  }

  const baseDrawCelestial=drawCelestial;
  drawCelestial=function(w,h){baseDrawCelestial(w,h);drawRoadster(w,h)};

  // Register before satellite-motion.js. On non-Roadster clicks this restores an
  // open Roadster card, then allows the aircraft/satellite handlers to continue.
  skyCanvas.addEventListener("click",event=>{
    if(typeof layers!=="undefined"&&layers.stars===false)return;
    if(typeof dragMoved!=="undefined"&&dragMoved)return;
    const rect=skyCanvas.getBoundingClientRect(),x=event.clientX-rect.left,y=event.clientY-rect.top;
    let best=null,bestDistance=Infinity;
    for(const target of roadsterHits){const distance=Math.hypot(x-target.x,y-target.y);if(distance<=target.r&&distance<bestDistance){best=target;bestDistance=distance}}
    if(!best){if(panelActive)restoreRoadsterContacts(false);return}
    event.stopImmediatePropagation();selectRoadster(best.item,true);
  },{capture:true});

  const previousShowObject=typeof showObject==="function"?showObject:null;
  if(previousShowObject){showObject=function(target){if(target?.kind==="deep_space"){selectRoadster(target.item,false);return}if(panelActive)restoreRoadsterContacts(false);return previousShowObject(target)}}
  const previousToggleTracking=typeof toggleTracking==="function"?toggleTracking:null;
  if(previousToggleTracking){toggleTracking=function(target){if(target?.kind==="deep_space")return selectRoadster(target.item,true);if(panelActive)restoreRoadsterContacts(false);return previousToggleTracking(target)}}

  window.NightAzimuthRoadster={drawRoadster,renderRoadsterContacts,selectRoadster,colour:ROADSTER_RED};
})();
