// Smooth satellite motion, status styling and Live Contacts detail.
// Satellites are unresolved point sources in Live Sky: keep their real projected
// azimuth/elevation while using only a subtle range cue for marker/halo size.
(function(){
  if(typeof drawContacts!=="function"||typeof skyXY!=="function")return;
  const skyCanvas=document.querySelector("#sky-canvas");
  if(!skyCanvas)return;

  const FRAME_INTERVAL_MS=33;
  const REDUCED_MOTION_INTERVAL_MS=100;
  const TRAIN_COUNT_UPDATE_MS=5000;
  const PANEL_UPDATE_MS=250;
  const EARTH_MU_KM3_S2=398600.4418;
  const EARTH_RADIUS_KM=6378.137;
  const preparedTracks=new WeakMap();
  let lastDraw=0;
  let lastTrainCountUpdate=0;
  let lastPanelUpdate=0;
  let lastCatalogue=null;
  let satelliteHits=[];
  let satellitePanelActive=false;
  let satellitePanelSignature="";

  const satelliteCanvas=document.querySelector("#satellite-canvas")||document.createElement("canvas");
  if(!satelliteCanvas.id){
    satelliteCanvas.id="satellite-canvas";
    satelliteCanvas.setAttribute("aria-hidden","true");
    skyCanvas.insertAdjacentElement("afterend",satelliteCanvas);
  }
  Object.assign(satelliteCanvas.style,{position:"absolute",inset:"0",width:"100%",height:"100%",pointerEvents:"none",userSelect:"none"});
  const satelliteCtx=satelliteCanvas.getContext("2d");
  if(!satelliteCtx)return;

  const contactsPanel=document.querySelector(".contacts-panel");
  const contactsTitle=contactsPanel?.querySelector(".section-head h2")||null;
  const contactsRoot=document.querySelector("#contacts");
  const aircraftDetail=document.querySelector("#aircraft-detail");
  const contactsBody=document.querySelector("#contacts-body");
  const defaultContactsTitle=contactsTitle?.textContent||"Aircraft";
  let satelliteDetail=document.querySelector("#satellite-contact-detail");
  if(!satelliteDetail&&contactsBody){
    satelliteDetail=document.createElement("div");
    satelliteDetail.id="satellite-contact-detail";
    satelliteDetail.className="contacts";
    satelliteDetail.hidden=true;
    contactsBody.insertBefore(satelliteDetail,contactsRoot||null);
  }

  const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));
  const finite=value=>{const number=Number(value);return Number.isFinite(number)?number:null};
  const shortestAzimuthDelta=(from,to)=>((to-from+540)%360)-180;

  function preparedTrack(satellite){
    const source=Array.isArray(satellite.track)?satellite.track:[];
    const cached=preparedTracks.get(satellite);
    if(cached&&cached.source===source)return cached.points;
    const points=source.map(point=>({
      time:Number.isFinite(point._nightazimuth_time)?point._nightazimuth_time:Date.parse(point.time_utc),
      azimuth:Number(point.azimuth_deg),
      elevation:Number(point.elevation_deg),
      range:Number(point.range_km)
    })).filter(point=>Number.isFinite(point.time)&&Number.isFinite(point.azimuth)&&Number.isFinite(point.elevation)&&Number.isFinite(point.range));
    preparedTracks.set(satellite,{source,points});
    return points;
  }

  function interpolateTrack(satellite,nowMs){
    const points=preparedTrack(satellite);
    if(points.length<2)return false;
    let leftIndex=0,rightIndex=1;
    const finalIndex=points.length-1;
    if(nowMs>=points[finalIndex].time){leftIndex=finalIndex-1;rightIndex=finalIndex}
    else if(nowMs>points[0].time){
      for(let i=0;i<finalIndex;i++){
        if(nowMs>=points[i].time&&nowMs<=points[i+1].time){leftIndex=i;rightIndex=i+1;break}
      }
    }
    const left=points[leftIndex],right=points[rightIndex];
    const span=Math.max(1,right.time-left.time);
    const ratio=clamp((nowMs-left.time)/span,0,1);
    satellite.azimuth_deg=(left.azimuth+shortestAzimuthDelta(left.azimuth,right.azimuth)*ratio+360)%360;
    satellite.elevation_deg=left.elevation+(right.elevation-left.elevation)*ratio;
    satellite.range_km=left.range+(right.range-left.range)*ratio;
    return true;
  }

  function updateTrainCounts(){
    const counts=new Map();
    for(const satellite of skySatellites){
      satellite.identification_status="Known tracked satellite";
      satellite.visible_train_count=null;
      if(satellite.category!=="Starlink"||!satellite.launch_id||Number(satellite.elevation_deg)<0)continue;
      counts.set(satellite.launch_id,(counts.get(satellite.launch_id)||0)+1);
    }
    for(const satellite of skySatellites){
      if(satellite.category==="Starlink"&&satellite.launch_id){
        const count=counts.get(satellite.launch_id)||0;
        satellite.visible_train_count=count>=2?count:null;
      }
    }
  }

  function sourceGroups(satellite){
    return new Set((Array.isArray(satellite?.source_groups)?satellite.source_groups:[]).map(group=>String(group).toUpperCase()));
  }

  function satelliteObjectType(satellite){
    const explicit=String(satellite?.object_type||"").trim().toUpperCase();
    if(explicit){
      if(explicit.includes("DEBRIS")||explicit==="DEB")return"Debris";
      if(explicit.includes("ROCKET")||explicit==="R/B"||explicit==="RB")return"Rocket body";
      if(explicit.includes("PAYLOAD")||explicit==="PAY")return"Payload";
      return explicit;
    }
    const name=String(satellite?.name||"").toUpperCase();
    if(/(?:^|[\s-])DEB(?:RIS)?(?:$|[\s-])/.test(name))return"Debris";
    if(/(?:^|\s)R\/B(?:$|\s)|ROCKET BODY/.test(name))return"Rocket body";
    return sourceGroups(satellite).has("ACTIVE")?"Payload / satellite":"Unknown";
  }

  function satelliteStatus(satellite){
    const groups=sourceGroups(satellite);
    const type=satelliteObjectType(satellite);
    const category=String(satellite?.category||"").toLowerCase();
    if(type==="Debris"||type==="Rocket body")return{key:"junk",label:type,color:"#929ca5",trail:"rgba(146,156,165,.22)"};
    if(groups.has("STATIONS")||category==="space station")return{key:"station",label:"Space station",color:"#f4fbff",trail:"rgba(244,251,255,.24)"};
    if(groups.has("LAST-30-DAYS")||category==="recent launch")return{key:"recent",label:"Recent launch",color:"#67d9ff",trail:"rgba(103,217,255,.28)"};
    if(groups.has("ACTIVE"))return{key:"active",label:"Active",color:"#79f2a6",trail:"rgba(121,242,166,.22)"};
    return{key:"unknown",label:"Tracked / status unknown",color:"#c9b46d",trail:"rgba(201,180,109,.20)"};
  }

  function trackedSatellite(satellite){
    if(typeof trackedObject==="undefined"||trackedObject?.kind!=="satellite")return false;
    const key=satellite.norad_id||satellite.name;
    return trackedObject.key===key;
  }

  function satelliteMarkerRadius(rangeKm,selected){
    const range=clamp(finite(rangeKm)??2000,250,45000);
    const minLog=Math.log10(250),maxLog=Math.log10(45000);
    const t=clamp((Math.log10(range)-minLog)/(maxLog-minLog),0,1);
    const radius=2.45-.70*t;
    return radius+(selected?1.05:0);
  }

  function ensureOverlaySize(){
    const w=skyCanvas.clientWidth||innerWidth,h=skyCanvas.clientHeight||innerHeight,dpr=Math.min(window.devicePixelRatio||1,2);
    const pixelWidth=Math.max(1,Math.round(w*dpr)),pixelHeight=Math.max(1,Math.round(h*dpr));
    if(satelliteCanvas.width!==pixelWidth||satelliteCanvas.height!==pixelHeight){satelliteCanvas.width=pixelWidth;satelliteCanvas.height=pixelHeight}
    satelliteCtx.setTransform(dpr,0,0,dpr,0,0);
    return{w,h};
  }

  function clearSatelliteOverlay(){
    const{w,h}=ensureOverlaySize();
    satelliteCtx.clearRect(0,0,w,h);
    satelliteHits=[];
  }

  function drawPredictedSatellitePaths(w,h){
    if(typeof layers!=="undefined"&&layers.satellites===false)return;
    satelliteCtx.save();
    satelliteCtx.lineWidth=.8;
    for(const satellite of skySatellites){
      if(!trackedSatellite(satellite)&&!skyXY(Number(satellite.azimuth_deg),Number(satellite.elevation_deg),w,h))continue;
      if(!trackedSatellite(satellite))continue;
      const track=Array.isArray(satellite.track)?satellite.track:[];
      if(track.length<2)continue;
      satelliteCtx.strokeStyle=satelliteStatus(satellite).trail;
      satelliteCtx.beginPath();
      const current=skyXY(Number(satellite.azimuth_deg),Number(satellite.elevation_deg),w,h);
      let drawing=false;
      if(current){satelliteCtx.moveTo(current[0],current[1]);drawing=true}
      for(const point of track){
        const xy=skyXY(Number(point.azimuth_deg),Number(point.elevation_deg),w,h);
        if(!xy){drawing=false;continue}
        if(!drawing){satelliteCtx.moveTo(xy[0],xy[1]);drawing=true}else satelliteCtx.lineTo(xy[0],xy[1]);
      }
      satelliteCtx.stroke();
    }
    satelliteCtx.restore();
  }

  function drawSatelliteMarker(satellite,x,y,selected){
    const status=satelliteStatus(satellite);
    const radius=satelliteMarkerRadius(satellite.range_km,selected);
    const halo=radius+(selected?5:2.8);
    satelliteCtx.save();
    satelliteCtx.fillStyle=status.color;
    satelliteCtx.shadowColor=status.color;
    satelliteCtx.shadowBlur=selected?8:3;
    satelliteCtx.globalAlpha=selected?.24:.13;
    satelliteCtx.beginPath();satelliteCtx.arc(x,y,halo,0,Math.PI*2);satelliteCtx.fill();
    satelliteCtx.globalAlpha=1;
    satelliteCtx.shadowBlur=selected?5:2;
    satelliteCtx.beginPath();satelliteCtx.arc(x,y,radius,0,Math.PI*2);satelliteCtx.fill();
    if(selected){
      satelliteCtx.shadowBlur=0;satelliteCtx.strokeStyle="#ffffff";satelliteCtx.lineWidth=1;
      satelliteCtx.beginPath();satelliteCtx.arc(x,y,halo+2,0,Math.PI*2);satelliteCtx.stroke();
    }
    if((typeof labels!=="undefined"&&labels.satellites)||selected){
      satelliteCtx.shadowBlur=0;satelliteCtx.fillStyle=selected?"#ffffff":status.color;
      satelliteCtx.font=selected?"bold 9px ui-monospace,monospace":"9px ui-monospace,monospace";
      satelliteCtx.textAlign="left";satelliteCtx.fillText(satellite.name||"SAT",x+7,y-6);
    }
    satelliteCtx.restore();
    return Math.max(8,halo+3);
  }

  function drawSatelliteLayer(){
    const{w,h}=ensureOverlaySize();
    satelliteCtx.clearRect(0,0,w,h);satelliteHits=[];
    if(typeof layers!=="undefined"&&layers.satellites===false)return;
    drawPredictedSatellitePaths(w,h);
    const visible=[];
    for(const satellite of skySatellites){
      const az=Number(satellite.azimuth_deg),el=Number(satellite.elevation_deg);
      if(!Number.isFinite(az)||!Number.isFinite(el))continue;
      const point=skyXY(az,el,w,h);if(!point)continue;
      visible.push({satellite,point,range:finite(satellite.range_km)??Infinity});
    }
    visible.sort((a,b)=>b.range-a.range);
    for(const entry of visible){
      const selected=trackedSatellite(entry.satellite);
      const radius=drawSatelliteMarker(entry.satellite,entry.point[0],entry.point[1],selected);
      satelliteHits.push({kind:"satellite",item:entry.satellite,x:entry.point[0],y:entry.point[1],r:radius});
    }
  }

  function motionDetails(satellite,nowMs=Date.now()){
    const points=preparedTrack(satellite);
    const az=finite(satellite.azimuth_deg),el=finite(satellite.elevation_deg);
    let next=null;
    for(const point of points){if(point.time>nowMs+1000){next=point;break}}
    if(az===null||el===null||!next)return{motion:null,angularSpeed:null};
    const seconds=Math.max(1,(next.time-nowMs)/1000);
    const deltaAz=shortestAzimuthDelta(az,next.azimuth)*Math.cos(((el+next.elevation)/2)*Math.PI/180);
    const deltaEl=next.elevation-el;
    const angularSpeed=Math.hypot(deltaAz,deltaEl)/seconds;
    const motion=deltaEl>.05?"Rising":deltaEl<-.05?"Setting":"Crossing";
    return{motion,angularSpeed};
  }

  function derivedOrbit(satellite){
    const period=finite(satellite.period_minutes),eccentricity=finite(satellite.eccentricity),inclination=finite(satellite.inclination_deg);
    if(period===null||period<=0)return{orbitClass:null,perigee:null,apogee:null};
    const e=clamp(eccentricity??0,0,.99),seconds=period*60;
    const semiMajor=Math.cbrt(EARTH_MU_KM3_S2*Math.pow(seconds/(2*Math.PI),2));
    const perigee=Math.max(0,semiMajor*(1-e)-EARTH_RADIUS_KM);
    const apogee=Math.max(0,semiMajor*(1+e)-EARTH_RADIUS_KM);
    let orbitClass;
    if(e>=.25&&apogee>2000)orbitClass="HEO";
    else if(period>=1350&&period<=1530)orbitClass=(inclination!==null&&Math.abs(inclination)<5&&e<.05)?"GEO":"GSO";
    else if(apogee<=2000)orbitClass="LEO";
    else if(perigee>2000&&apogee<36000)orbitClass="MEO";
    else orbitClass="High Earth orbit";
    return{orbitClass,perigee,apogee};
  }

  function makeDetailRow(label,value){
    if(value===null||value===undefined||value==="")return null;
    const row=document.createElement("div"),key=document.createElement("span"),data=document.createElement("strong");
    key.textContent=label;data.textContent=String(value);row.append(key,data);return row;
  }

  function makeSection(title,rows){
    const content=rows.filter(Boolean);if(!content.length)return null;
    const section=document.createElement("section"),heading=document.createElement("p");
    heading.className="eyebrow";heading.textContent=title;section.append(heading,...content);return section;
  }

  function formatEpoch(value){
    if(!value)return null;
    const date=new Date(value);return Number.isNaN(date.getTime())?String(value):date.toLocaleString();
  }

  function predictedPosition(satellite,seconds){
    const points=preparedTrack(satellite);
    if(!points.length)return null;
    const target=Date.now()+seconds*1000;
    let best=points[points.length-1];
    for(const point of points){if(point.time>=target){best=point;break}}
    return`Az ${best.azimuth.toFixed(1)}° · El ${best.elevation.toFixed(1)}°`;
  }

  function selectedSatellite(){
    if(typeof trackedObject==="undefined"||trackedObject?.kind!=="satellite")return null;
    return (Array.isArray(skySatellites)?skySatellites:[]).find(item=>(item.norad_id||item.name)===trackedObject.key)||null;
  }

  function renderSatelliteContacts(satellite){
    if(!satelliteDetail||!satellite)return;
    const status=satelliteStatus(satellite),type=satelliteObjectType(satellite),groups=sourceGroups(satellite),motion=motionDetails(satellite),orbit=derivedOrbit(satellite);
    const signature=[satellite.norad_id,satellite.name,status.key,Number(satellite.azimuth_deg).toFixed(1),Number(satellite.elevation_deg).toFixed(1),Number(satellite.range_km).toFixed(1),motion.motion,motion.angularSpeed==null?"":motion.angularSpeed.toFixed(2)].join("|");
    if(signature===satellitePanelSignature&&satellitePanelActive)return;
    satellitePanelSignature=signature;satellitePanelActive=true;
    if(contactsTitle)contactsTitle.textContent="Satellite";
    if(contactsRoot)contactsRoot.hidden=true;
    if(aircraftDetail)aircraftDetail.hidden=true;
    satelliteDetail.hidden=false;

    const statusLine=document.createElement("p");statusLine.className="muted";statusLine.style.color=status.color;statusLine.textContent=`● ${status.label.toUpperCase()}`;
    const sections=[
      makeSection("IDENTIFICATION",[
        makeDetailRow("Name",satellite.name),
        makeDetailRow("NORAD catalogue ID",satellite.norad_id),
        makeDetailRow("International designator",satellite.object_id),
        makeDetailRow("Object type",type),
        makeDetailRow("Status",status.label),
        makeDetailRow("Category",satellite.category),
        makeDetailRow("Launch / train",satellite.launch_id),
        makeDetailRow("Visible in same Starlink launch",satellite.visible_train_count)
      ]),
      makeSection("POSITION",[
        makeDetailRow("Azimuth",finite(satellite.azimuth_deg)==null?null:`${Number(satellite.azimuth_deg).toFixed(2)}°`),
        makeDetailRow("Elevation",finite(satellite.elevation_deg)==null?null:`${Number(satellite.elevation_deg).toFixed(2)}°`),
        makeDetailRow("Slant range",finite(satellite.range_km)==null?null:`${Number(satellite.range_km).toFixed(1)} km`),
        makeDetailRow("Motion",motion.motion),
        makeDetailRow("Angular speed",motion.angularSpeed==null?null:`${motion.angularSpeed.toFixed(2)}°/s`)
      ]),
      makeSection("ORBIT",[
        makeDetailRow("Orbit class (derived)",orbit.orbitClass),
        makeDetailRow("Inclination",satellite.inclination_deg==null?null:`${Number(satellite.inclination_deg).toFixed(2)}°`),
        makeDetailRow("Orbital period",satellite.period_minutes==null?null:`${Number(satellite.period_minutes).toFixed(2)} min`),
        makeDetailRow("Eccentricity",satellite.eccentricity),
        makeDetailRow("Perigee (derived)",orbit.perigee==null?null:`${Math.round(orbit.perigee).toLocaleString()} km`),
        makeDetailRow("Apogee (derived)",orbit.apogee==null?null:`${Math.round(orbit.apogee).toLocaleString()} km`),
        makeDetailRow("Element epoch",formatEpoch(satellite.epoch_utc))
      ]),
      makeSection("CATALOGUE",[
        makeDetailRow("Active catalogue",groups.has("ACTIVE")?"Yes":"No"),
        makeDetailRow("Recent launch",groups.has("LAST-30-DAYS")?"Yes":"No"),
        makeDetailRow("Bright / visual",groups.has("VISUAL")?"Yes":"No"),
        makeDetailRow("Space-station catalogue",groups.has("STATIONS")?"Yes":"No"),
        makeDetailRow("Catalogues",Array.from(groups).join(", "))
      ]),
      makeSection("PREDICTED TRACK",[
        makeDetailRow("In 10 seconds",predictedPosition(satellite,10)),
        makeDetailRow("In 30 seconds",predictedPosition(satellite,30)),
        makeDetailRow("In 60 seconds",predictedPosition(satellite,60))
      ])
    ].filter(Boolean);
    const back=document.createElement("button");back.type="button";back.textContent="Back to aircraft";back.addEventListener("click",()=>restoreAircraftContacts(true));
    satelliteDetail.replaceChildren(statusLine,...sections,back);
  }

  function restoreAircraftContacts(clearSatelliteTracking=false){
    satellitePanelActive=false;satellitePanelSignature="";
    if(clearSatelliteTracking&&typeof trackedObject!=="undefined"&&trackedObject?.kind==="satellite")trackedObject=null;
    if(contactsTitle)contactsTitle.textContent=defaultContactsTitle;
    if(satelliteDetail)satelliteDetail.hidden=true;
    if(contactsRoot)contactsRoot.hidden=false;
    if(aircraftDetail)aircraftDetail.hidden=false;
  }

  function selectSatellite(satellite,toggle=false){
    if(!satellite)return false;
    const key=satellite.norad_id||satellite.name;
    const already=typeof trackedObject!=="undefined"&&trackedObject?.kind==="satellite"&&trackedObject.key===key;
    if(toggle&&already){restoreAircraftContacts(true);return false}
    trackedObject={kind:"satellite",key};
    renderSatelliteContacts(satellite);
    return true;
  }

  const originalDrawContacts=drawContacts;
  drawContacts=function(w,h){
    if(typeof layers==="undefined")return originalDrawContacts(w,h);
    const previous=layers.satellites;
    try{layers.satellites=false;return originalDrawContacts(w,h)}finally{layers.satellites=previous}
  };

  const originalShowObject=typeof showObject==="function"?showObject:null;
  if(originalShowObject){
    showObject=function(target){
      if(target?.kind==="satellite"){selectSatellite(target.item,false);return}
      restoreAircraftContacts(false);return originalShowObject(target);
    };
  }

  const originalToggleTracking=typeof toggleTracking==="function"?toggleTracking:null;
  if(originalToggleTracking){
    toggleTracking=function(target){
      if(target?.kind==="satellite")return selectSatellite(target.item,true);
      restoreAircraftContacts(false);return originalToggleTracking(target);
    };
  }

  const originalUpdateTrackedView=typeof updateTrackedView==="function"?updateTrackedView:null;
  if(originalUpdateTrackedView){
    updateTrackedView=function(){
      if(typeof trackedObject!=="undefined"&&trackedObject?.kind==="satellite")return;
      return originalUpdateTrackedView();
    };
  }

  skyCanvas.addEventListener("click",event=>{
    if(typeof layers!=="undefined"&&layers.satellites===false)return;
    if(typeof dragMoved!=="undefined"&&dragMoved)return;
    const rect=skyCanvas.getBoundingClientRect(),x=event.clientX-rect.left,y=event.clientY-rect.top;
    let best=null,bestDistance=Infinity;
    for(const target of satelliteHits){const distance=Math.hypot(x-target.x,y-target.y);if(distance<=target.r&&distance<bestDistance){best=target;bestDistance=distance}}
    if(!best)return;
    event.stopImmediatePropagation();selectSatellite(best.item,true);
  },{capture:true});

  function animate(now){
    const reduced=window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
    const interval=reduced?REDUCED_MOTION_INTERVAL_MS:FRAME_INTERVAL_MS;
    if(!document.hidden&&now-lastDraw>=interval){
      const current=Date.now();
      const layerVisible=typeof layers!=="undefined"&&layers.satellites!==false;
      if(layerVisible||selectedSatellite()){
        for(const satellite of skySatellites)interpolateTrack(satellite,current);
        if(lastCatalogue!==skySatellites||current-lastTrainCountUpdate>=TRAIN_COUNT_UPDATE_MS){
          updateTrainCounts();lastCatalogue=skySatellites;lastTrainCountUpdate=current;
        }
        drawSatelliteLayer();
        if(current-lastPanelUpdate>=PANEL_UPDATE_MS){const selected=selectedSatellite();if(selected)renderSatelliteContacts(selected);lastPanelUpdate=current}
      }else clearSatelliteOverlay();
      lastDraw=now;
    }
    requestAnimationFrame(animate);
  }

  // Clear any legacy diamond satellite markers painted before this wrapper loaded.
  requestAnimationFrame(()=>{if(typeof drawSky==="function")drawSky()});
  requestAnimationFrame(animate);

  window.NightAzimuthSatellites={satelliteStatus,satelliteObjectType,satelliteMarkerRadius,derivedOrbit,motionDetails,drawSatelliteLayer};
})();
