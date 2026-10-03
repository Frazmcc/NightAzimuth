(()=>{
if(typeof drawContacts!=="function"||typeof drawSky!=="function"||typeof skyXY!=="function")return;
if(window.__nightAzimuthAircraftPerspectiveLoaded)return;
window.__nightAzimuthAircraftPerspectiveLoaded=true;

const skyCanvas=document.querySelector("#sky-canvas");
if(!skyCanvas)return;

const KM_PER_MILE=1.609344;
const MAX_RANGE_MILES=50;
const MAX_RANGE_KM=MAX_RANGE_MILES*KM_PER_MILE;
const MIN_MODEL_SIZE=7.5;
const MAX_MODEL_SIZE=24;
const MAX_PREDICTION_SECONDS=15;
const SNAPSHOT_CORRECTION_SECONDS=.75;
const FRAME_INTERVAL_MS=33;
const REDUCED_MOTION_INTERVAL_MS=100;
const MIN_FORWARD_PROJECTION=.18;
const MIN_LATERAL_PROJECTION=.34;
const MIN_VERTICAL_PROJECTION=.16;
const DEG=Math.PI/180;
const baseDrawContacts=drawContacts;
const motionEpochs=new Map();
const renderedStates=new Map();
const preparedTracks=new WeakMap();
let lastCleanup=0;
let lastDraw=0;
let aircraftHits=[];
let queuedLabels=[];
let labelBoxes=[];

const aircraftCanvas=document.querySelector("#aircraft-canvas")||document.createElement("canvas");
if(!aircraftCanvas.id){
  aircraftCanvas.id="aircraft-canvas";
  aircraftCanvas.setAttribute("aria-hidden","true");
  skyCanvas.insertAdjacentElement("afterend",aircraftCanvas);
}
Object.assign(aircraftCanvas.style,{position:"absolute",inset:"0",width:"100%",height:"100%",pointerEvents:"none",userSelect:"none"});
const aircraftCtx=aircraftCanvas.getContext("2d");
if(!aircraftCtx)return;

const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));
const finite=value=>{const number=Number(value);return Number.isFinite(number)?number:null};
function aircraftIdentity(aircraft,index=""){
  const icao=String(aircraft?.icao24||"").trim().toLowerCase();
  if(icao)return `icao:${icao}`;
  const registration=String(aircraft?.registration||"").trim().toUpperCase();
  if(registration)return `registration:${registration}`;
  const callsign=String(aircraft?.callsign||"").trim().toUpperCase();
  if(callsign)return `callsign:${callsign}`;
  return `anonymous:${index}`;
}
function contactAgeSeconds(aircraft){
  const age=finite(aircraft?.position_age_seconds);
  return age===null?Number.POSITIVE_INFINITY:Math.max(0,age);
}
function uniqueAircraftContacts(contacts){
  const unique=new Map();
  for(let index=0;index<contacts.length;index++){
    const aircraft=contacts[index];
    const key=aircraftIdentity(aircraft,index);
    const existing=unique.get(key);
    if(!existing||contactAgeSeconds(aircraft)<contactAgeSeconds(existing.aircraft)){
      unique.set(key,{aircraft,index});
    }
  }
  return [...unique.values()].sort((a,b)=>a.index-b.index).map(entry=>entry.aircraft);
}
const shortestAngle=(from,to)=>((to-from+540)%360)-180;
const dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
const add=(a,b)=>[a[0]+b[0],a[1]+b[1],a[2]+b[2]];
const scale=(a,s)=>[a[0]*s,a[1]*s,a[2]*s];
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
function unit(vector){
  const length=Math.hypot(vector[0],vector[1],vector[2]);
  return length>1e-9?scale(vector,1/length):[0,0,0];
}
function unit2(vector,fallback=[1,0]){
  const length=Math.hypot(vector[0],vector[1]);
  return length>1e-9?[vector[0]/length,vector[1]/length]:fallback;
}

function perspectiveEnabled(){
  return localStorage.getItem("nightazimuth.aircraftMarkerStyle")!=="dot";
}

function aircraftKind(aircraft){
  const category=String(aircraft?.category||"").toUpperCase();
  const type=String(aircraft?.type_code||"").toUpperCase();
  const description=String(aircraft?.type_description||aircraft?.display?.make_model||"").toLowerCase();
  if(category==="A7"||/helicopter|rotorcraft/.test(description))return"helicopter";
  if(category==="B1"||/glider/.test(description))return"glider";
  if(category==="B6"||/drone|uav/.test(description))return"drone";
  if(category==="A1"||category==="A2"||/cessna|piper|beech|light aircraft/.test(description))return"light";
  return"fixed";
}

function aircraftProfile(aircraft){
  const kind=aircraftKind(aircraft);
  if(kind!=="fixed")return kind;
  const type=String(aircraft?.type_code||"").toUpperCase();
  const description=String(aircraft?.type_description||aircraft?.display?.make_model||"").toLowerCase();
  const text=`${type} ${description}`;
  if(aircraft?.military&&/fighter|typhoon|tornado|f-\d|rafale|gripen|hawk|alphajet/.test(text))return"military";
  if(/A33|A34|A35|A38|B74|B76|B77|B78|MD11|DC10|wide.?body/.test(text))return"widebody";
  if(/AT4|AT7|ATR|DH8|DHC8|Q400|SF34|SAAB 340|turboprop/.test(text))return"turboprop";
  if(/E17|E19|E75|E90|E95|CRJ|regional/.test(text))return"regional";
  if(/C25|C5[56]|C6[568]|GLF|LJ|FA[579]|E35|E50|E55|citation|gulfstream|learjet|falcon|business jet/.test(text))return"business";
  if(/A31|A32|B73|BCS|A220|airbus|boeing|airliner|jet/.test(text))return"narrowbody";
  return"generic";
}

function fixedWingGeometry(profile){
  const config={
    glider:{wing:1.28,body:1.76,tail:.30,tipX:-.03,rootFront:.12,rootBack:-.19},
    light:{wing:.72,body:1.82,tail:.34,tipX:-.10,rootFront:.15,rootBack:-.21},
    regional:{wing:.90,body:2.02,tail:.39,tipX:-.15,rootFront:.18,rootBack:-.24},
    turboprop:{wing:1.03,body:1.96,tail:.41,tipX:-.10,rootFront:.16,rootBack:-.23},
    business:{wing:.76,body:1.86,tail:.34,tipX:-.13,rootFront:.17,rootBack:-.22},
    widebody:{wing:1.13,body:2.31,tail:.49,tipX:-.19,rootFront:.21,rootBack:-.28},
    military:{wing:.80,body:1.74,tail:.34,tipX:-.05,rootFront:.08,rootBack:-.24},
    narrowbody:{wing:.98,body:2.15,tail:.42,tipX:-.18,rootFront:.18,rootBack:-.24},
    generic:{wing:.90,body:2.00,tail:.39,tipX:-.15,rootFront:.17,rootBack:-.23}
  }[profile]||{wing:.90,body:2.00,tail:.39,tipX:-.15,rootFront:.17,rootBack:-.23};
  const noseX=config.body*.55;
  const tailX=-config.body*.45;
  const tailRootFront=tailX+.26,tailRootBack=tailX+.02;
  const rightWing=[[config.rootFront,0,0],[config.tipX,config.wing,0],[config.rootBack,config.wing*.84,0],[config.rootBack,0,0]];
  const leftWing=[[config.rootFront,0,0],[config.tipX,-config.wing,0],[config.rootBack,-config.wing*.84,0],[config.rootBack,0,0]];
  const rightTail=[[tailRootFront,0,0],[tailRootBack,config.tail,0],[tailX-.08,config.tail*.82,0],[tailRootBack,0,0]];
  const leftTail=[[tailRootFront,0,0],[tailRootBack,-config.tail,0],[tailX-.08,-config.tail*.82,0],[tailRootBack,0,0]];
  const finHeight=profile==="military"?.40:profile==="widebody"?.52:.48;
  const fin=[[tailX+.18,0,.02],[tailX-.02,0,finHeight],[tailX-.18,0,.06]];
  return{
    profile,...config,noseX,tailX,rightWing,leftWing,rightTail,leftTail,fin,
    portTip:[config.tipX,-config.wing,.02],starboardTip:[config.tipX,config.wing,.02],tailLight:[tailX-.08,0,.08],
    landmarks:[[noseX,0,0],[tailX,0,0],[config.tipX,config.wing,0],[config.tipX,-config.wing,0],[tailX-.08,config.tail,0],[tailX-.08,-config.tail,0],[tailX-.02,0,finHeight]]
  };
}

function modelSize(rangeKm,selected){
  const miles=clamp((finite(rangeKm)??MAX_RANGE_KM)/KM_PER_MILE,0,MAX_RANGE_MILES);
  const t=miles/MAX_RANGE_MILES;
  const eased=t*t*(3-2*t);
  return MAX_MODEL_SIZE-(MAX_MODEL_SIZE-MIN_MODEL_SIZE)*eased+(selected?2:0);
}

function contactFingerprint(aircraft){
  const track=Array.isArray(aircraft?.future_track)?aircraft.future_track:[];
  const first=track[0]||{};
  const last=track[track.length-1]||{};
  return [finite(aircraft?.azimuth_deg)?.toFixed(5),finite(aircraft?.elevation_deg)?.toFixed(5),finite(aircraft?.range_km)?.toFixed(4),finite(aircraft?.position_age_seconds)?.toFixed(2),finite(first.azimuth_deg)?.toFixed(5),finite(first.elevation_deg)?.toFixed(5),finite(last.azimuth_deg)?.toFixed(5),finite(last.elevation_deg)?.toFixed(5),finite(last.seconds_from_now)?.toFixed(2)].join("|");
}

function motionEpoch(aircraft,nowMs){
  const key=aircraftIdentity(aircraft);
  const fingerprint=contactFingerprint(aircraft);
  let entry=motionEpochs.get(key);
  if(!entry||entry.fingerprint!==fingerprint){
    const previous=renderedStates.get(key)||null;
    entry={fingerprint,receivedAt:nowMs,lastSeenAt:nowMs,correctionFrom:previous,correction:null};
    motionEpochs.set(key,entry);
  }else entry.lastSeenAt=nowMs;
  return{key,entry};
}

function snapshotCorrection(from,target){
  if(!from)return null;
  return{
    azimuth:shortestAngle(target.azimuth,from.azimuth),
    elevation:from.elevation-target.elevation,
    rangeKm:from.rangeKm-target.rangeKm,
    heading:shortestAngle(target.heading,from.heading),
    roll:from.roll-target.roll,
    flightPathDeg:from.flightPathDeg-target.flightPathDeg
  };
}

function applySnapshotCorrection(target,correction,elapsed){
  if(!correction)return target;
  const t=clamp(elapsed/SNAPSHOT_CORRECTION_SECONDS,0,1);
  const remaining=1-(t*t*(3-2*t));
  return{
    ...target,
    azimuth:(target.azimuth+correction.azimuth*remaining+360)%360,
    elevation:target.elevation+correction.elevation*remaining,
    rangeKm:target.rangeKm+correction.rangeKm*remaining,
    heading:(target.heading+correction.heading*remaining+360)%360,
    roll:target.roll+correction.roll*remaining,
    flightPathDeg:target.flightPathDeg+correction.flightPathDeg*remaining
  };
}

function preparedTrack(aircraft){
  const source=Array.isArray(aircraft?.future_track)?aircraft.future_track:[];
  const cached=preparedTracks.get(aircraft);
  if(cached&&cached.source===source)return cached.points;
  const points=source.map(point=>({
    seconds:finite(point?.seconds_from_now),
    azimuth:finite(point?.azimuth_deg),
    elevation:finite(point?.elevation_deg)
  })).filter(point=>point.seconds!==null&&point.azimuth!==null&&point.elevation!==null).sort((a,b)=>a.seconds-b.seconds);
  preparedTracks.set(aircraft,{source,points});
  return points;
}

function interpolateTrack(aircraft,nowMs){
  const{key,entry}=motionEpoch(aircraft,nowMs);
  const elapsed=clamp((nowMs-entry.receivedAt)/1000,0,MAX_PREDICTION_SECONDS);
  const points=preparedTrack(aircraft);
  let azimuth=finite(aircraft?.azimuth_deg),elevation=finite(aircraft?.elevation_deg);
  if(points.length){
    if(elapsed<=points[0].seconds){azimuth=points[0].azimuth;elevation=points[0].elevation}
    else if(elapsed>=points[points.length-1].seconds){azimuth=points[points.length-1].azimuth;elevation=points[points.length-1].elevation}
    else{
      for(let i=0;i<points.length-1;i++){
        const left=points[i],right=points[i+1];
        if(elapsed<left.seconds||elapsed>right.seconds)continue;
        const span=Math.max(.001,right.seconds-left.seconds);
        const ratio=clamp((elapsed-left.seconds)/span,0,1);
        azimuth=(left.azimuth+shortestAngle(left.azimuth,right.azimuth)*ratio+360)%360;
        elevation=left.elevation+(right.elevation-left.elevation)*ratio;
        break;
      }
    }
  }
  const trackDeg=finite(aircraft?.track_deg),trueHeading=finite(aircraft?.true_heading_deg),magneticHeading=finite(aircraft?.magnetic_heading_deg),turnRate=finite(aircraft?.track_rate_deg_s);
  const baseHeading=trueHeading??trackDeg??magneticHeading??0;
  const heading=(baseHeading+(turnRate??0)*elapsed+360)%360;
  const speed=finite(aircraft?.ground_speed_mps),verticalRate=finite(aircraft?.vertical_rate_mps);
  const flightPathDeg=speed!==null&&speed>1&&verticalRate!==null?clamp(Math.atan2(verticalRate,speed)/DEG,-20,20):0;
  let rangeKm=finite(aircraft?.range_km)??MAX_RANGE_KM;
  if(trackDeg!==null&&speed!==null&&azimuth!==null){
    const horizontalRadial=speed*Math.cos(shortestAngle(azimuth,trackDeg)*DEG);
    const elevationRad=(elevation??0)*DEG;
    const verticalRadial=(verticalRate??0)*Math.sin(elevationRad);
    rangeKm=clamp(rangeKm+(horizontalRadial*Math.cos(elevationRad)+verticalRadial)*elapsed/1000,0,MAX_RANGE_KM);
  }
  let state={azimuth,elevation,rangeKm,heading,roll:clamp(finite(aircraft?.roll_deg)??0,-89,89),flightPathDeg,elapsed};
  if(entry.correctionFrom&&!entry.correction)entry.correction=snapshotCorrection(entry.correctionFrom,state);
  if(entry.correction&&elapsed<SNAPSHOT_CORRECTION_SECONDS)state=applySnapshotCorrection(state,entry.correction,elapsed);
  else if(entry.correction){entry.correction=null;entry.correctionFrom=null}
  if(state.azimuth!==null&&state.elevation!==null)renderedStates.set(key,{...state});
  return state;
}

function cameraBasis(azimuthDeg,elevationDeg){
  const az=azimuthDeg*DEG,el=elevationDeg*DEG;
  return{los:[Math.sin(az)*Math.cos(el),Math.cos(az)*Math.cos(el),Math.sin(el)],right:[Math.cos(az),-Math.sin(az),0],up:[-Math.sin(az)*Math.sin(el),-Math.cos(az)*Math.sin(el),Math.cos(el)]};
}

function aircraftBasis(headingDeg,flightPathDeg,rollDeg){
  const heading=headingDeg*DEG,gamma=flightPathDeg*DEG;
  const forward=unit([Math.sin(heading)*Math.cos(gamma),Math.cos(heading)*Math.cos(gamma),Math.sin(gamma)]);
  const worldUp=[0,0,1];
  const right0=unit(cross(forward,worldUp));
  const up0=unit(cross(right0,forward));
  const roll=rollDeg*DEG;
  const right=add(scale(right0,Math.cos(roll)),scale(up0,-Math.sin(roll)));
  const up=add(scale(up0,Math.cos(roll)),scale(right0,Math.sin(roll)));
  return{forward,right:unit(right),up:unit(up)};
}

function readableAxis(axis,fallback,minMagnitude){
  const magnitude=Math.hypot(axis[0],axis[1]);
  if(magnitude>=minMagnitude)return axis;
  const fallbackUnit=unit2(fallback,[1,0]);
  const axisUnit=magnitude>1e-6?unit2(axis,fallbackUnit):fallbackUnit;
  const blend=1-clamp(magnitude/minMagnitude,0,1);
  const direction=unit2([axisUnit[0]*(1-blend)+fallbackUnit[0]*blend,axisUnit[1]*(1-blend)+fallbackUnit[1]*blend],fallbackUnit);
  return[direction[0]*minMagnitude,direction[1]*minMagnitude];
}

function projectionFrame(basis,camera){
  const forward=[dot(basis.forward,camera.right),-dot(basis.forward,camera.up)];
  const lateral=[dot(basis.right,camera.right),-dot(basis.right,camera.up)];
  const vertical=[dot(basis.up,camera.right),-dot(basis.up,camera.up)];
  const readableForward=readableAxis(forward,[0,-1],MIN_FORWARD_PROJECTION);
  const lateralFallback=unit2([-readableForward[1],readableForward[0]],[1,0]);
  const readableLateral=readableAxis(lateral,lateralFallback,MIN_LATERAL_PROJECTION);
  const verticalFallback=unit2([-readableLateral[1],readableLateral[0]],[0,-1]);
  const readableVertical=readableAxis(vertical,verticalFallback,MIN_VERTICAL_PROJECTION);
  return{forward:readableForward,lateral:readableLateral,vertical:readableVertical};
}

function projectLocal(local,basis,camera,size,originX,originY){
  const frame=projectionFrame(basis,camera);
  const sx=local[0]*frame.forward[0]+local[1]*frame.lateral[0]+local[2]*frame.vertical[0];
  const sy=local[0]*frame.forward[1]+local[1]*frame.lateral[1]+local[2]*frame.vertical[1];
  const world=add(add(scale(basis.forward,local[0]),scale(basis.right,local[1])),scale(basis.up,local[2]));
  const depth=dot(world,camera.los);
  return[originX+sx*size,originY+sy*size,depth];
}

function pathFromLocal(points,basis,camera,size,x,y){
  const projected=points.map(point=>projectLocal(point,basis,camera,size,x,y));
  if(!projected.length)return projected;
  aircraftCtx.beginPath();aircraftCtx.moveTo(projected[0][0],projected[0][1]);
  for(let i=1;i<projected.length;i++)aircraftCtx.lineTo(projected[i][0],projected[i][1]);
  aircraftCtx.closePath();
  return projected;
}

function drawSurface(points,basis,camera,size,x,y,stroke,fill,lineWidth){
  pathFromLocal(points,basis,camera,size,x,y);
  aircraftCtx.fillStyle=fill;aircraftCtx.strokeStyle=stroke;aircraftCtx.lineWidth=lineWidth;aircraftCtx.fill();aircraftCtx.stroke();
}

function drawNavigationLights(geometry,basis,camera,size,x,y){
  const lights=[
    {point:geometry.portTip,fill:"#ff5b66",shadow:"#ff3344"},
    {point:geometry.starboardTip,fill:"#71ff9b",shadow:"#23e86b"},
    {point:geometry.tailLight,fill:"#f7fbff",shadow:"#dff8ff"}
  ];
  aircraftCtx.save();
  for(const light of lights){
    const p=projectLocal(light.point,basis,camera,size,x,y);
    aircraftCtx.fillStyle=light.fill;aircraftCtx.shadowColor=light.shadow;aircraftCtx.shadowBlur=4;
    aircraftCtx.beginPath();aircraftCtx.arc(p[0],p[1],clamp(size*.05,.85,1.45),0,Math.PI*2);aircraftCtx.fill();
  }
  aircraftCtx.restore();
}

function drawFixedWingModel(geometry,basis,camera,size,x,y,stroke,glow,selected){
  aircraftCtx.save();
  aircraftCtx.shadowColor=glow;aircraftCtx.shadowBlur=selected?10:4;aircraftCtx.lineJoin="round";aircraftCtx.lineCap="round";
  const surfaceWidth=selected?1.7:1.05;
  const surfaceFill=selected?"rgba(225,249,255,.20)":"rgba(105,216,239,.11)";
  drawSurface(geometry.leftWing,basis,camera,size,x,y,stroke,surfaceFill,surfaceWidth);
  drawSurface(geometry.rightWing,basis,camera,size,x,y,stroke,surfaceFill,surfaceWidth);
  drawSurface(geometry.leftTail,basis,camera,size,x,y,stroke,"rgba(105,216,239,.09)",surfaceWidth);
  drawSurface(geometry.rightTail,basis,camera,size,x,y,stroke,"rgba(105,216,239,.09)",surfaceWidth);
  drawSurface(geometry.fin,basis,camera,size,x,y,stroke,"rgba(160,235,250,.15)",surfaceWidth);
  const nose=projectLocal([geometry.noseX,0,0],basis,camera,size,x,y),tail=projectLocal([geometry.tailX,0,0],basis,camera,size,x,y);
  aircraftCtx.beginPath();aircraftCtx.moveTo(tail[0],tail[1]);aircraftCtx.lineTo(nose[0],nose[1]);aircraftCtx.strokeStyle="rgba(3,14,22,.92)";aircraftCtx.lineWidth=Math.max(selected?4.8:4.0,size*(geometry.profile==="light"?.18:.16));aircraftCtx.stroke();
  aircraftCtx.beginPath();aircraftCtx.moveTo(tail[0],tail[1]);aircraftCtx.lineTo(nose[0],nose[1]);aircraftCtx.strokeStyle=stroke;aircraftCtx.lineWidth=Math.max(selected?2.4:1.8,size*.075);aircraftCtx.stroke();
  aircraftCtx.fillStyle=selected?"rgba(240,253,255,.95)":stroke;aircraftCtx.beginPath();aircraftCtx.arc(nose[0],nose[1],selected?1.7:1.25,0,Math.PI*2);aircraftCtx.fill();
  aircraftCtx.restore();
  drawNavigationLights(geometry,basis,camera,size,x,y);
}

const HELI_LANDMARKS=[[.62,0,0],[-1.05,0,0],[0,1.05,.12],[0,-1.05,.12],[.82,0,.12],[-.82,0,.12]];
const DRONE_LANDMARKS=[[.55,.55,0],[.55,-.55,0],[-.55,.55,0],[-.55,-.55,0]];

function drawHelicopterModel(basis,camera,size,x,y,stroke,glow,selected){
  aircraftCtx.save();aircraftCtx.strokeStyle=stroke;aircraftCtx.fillStyle="rgba(8,26,36,.82)";aircraftCtx.shadowColor=glow;aircraftCtx.shadowBlur=selected?10:4;aircraftCtx.lineWidth=selected?2:1.35;
  const body=[[.48,.16,0],[.62,0,0],[.30,-.18,0],[-.36,-.14,0],[-.54,0,0],[-.36,.14,0]];
  pathFromLocal(body,basis,camera,size,x,y);aircraftCtx.fill();aircraftCtx.stroke();
  const tailA=projectLocal([-.45,0,0],basis,camera,size,x,y),tailB=projectLocal([-1.05,0,0],basis,camera,size,x,y);
  aircraftCtx.beginPath();aircraftCtx.moveTo(tailA[0],tailA[1]);aircraftCtx.lineTo(tailB[0],tailB[1]);aircraftCtx.stroke();
  const rotorL=projectLocal([0,-1.05,.12],basis,camera,size,x,y),rotorR=projectLocal([0,1.05,.12],basis,camera,size,x,y),rotorF=projectLocal([.82,0,.12],basis,camera,size,x,y),rotorB=projectLocal([-.82,0,.12],basis,camera,size,x,y);
  aircraftCtx.globalAlpha=.72;aircraftCtx.beginPath();aircraftCtx.moveTo(rotorL[0],rotorL[1]);aircraftCtx.lineTo(rotorR[0],rotorR[1]);aircraftCtx.moveTo(rotorF[0],rotorF[1]);aircraftCtx.lineTo(rotorB[0],rotorB[1]);aircraftCtx.stroke();aircraftCtx.restore();
}

function drawDroneModel(basis,camera,size,x,y,stroke,glow,selected){
  aircraftCtx.save();aircraftCtx.strokeStyle=stroke;aircraftCtx.fillStyle="rgba(8,26,36,.82)";aircraftCtx.shadowColor=glow;aircraftCtx.shadowBlur=selected?10:4;aircraftCtx.lineWidth=selected?2:1.3;
  const centre=projectLocal([0,0,0],basis,camera,size,x,y);
  for(const point of DRONE_LANDMARKS){const tip=projectLocal(point,basis,camera,size,x,y);aircraftCtx.beginPath();aircraftCtx.moveTo(centre[0],centre[1]);aircraftCtx.lineTo(tip[0],tip[1]);aircraftCtx.stroke();aircraftCtx.beginPath();aircraftCtx.arc(tip[0],tip[1],Math.max(1.5,size*.12),0,Math.PI*2);aircraftCtx.stroke()}
  aircraftCtx.beginPath();aircraftCtx.arc(centre[0],centre[1],Math.max(2,size*.16),0,Math.PI*2);aircraftCtx.fill();aircraftCtx.stroke();aircraftCtx.restore();
}

function projectedBounds(locals,basis,camera,size,x,y){
  const points=locals.map(point=>projectLocal(point,basis,camera,size,x,y));
  return{minX:Math.min(...points.map(p=>p[0])),maxX:Math.max(...points.map(p=>p[0])),minY:Math.min(...points.map(p=>p[1])),maxY:Math.max(...points.map(p=>p[1]))};
}

function boxesOverlap(a,b){
  return !(a.right+3<b.left||a.left-3>b.right||a.bottom+3<b.top||a.top-3>b.bottom);
}

function drawAircraftLabels(w,h){
  labelBoxes=[];
  queuedLabels.sort((a,b)=>Number(b.selected)-Number(a.selected));
  for(const label of queuedLabels){
    aircraftCtx.save();
    aircraftCtx.font=label.selected?"bold 10px ui-monospace,monospace":"10px ui-monospace,monospace";
    aircraftCtx.textBaseline="middle";
    const width=aircraftCtx.measureText(label.text).width,height=12;
    const candidates=[
      {side:"right",x:label.bounds.maxX+8,y:label.bounds.minY-5},
      {side:"right",x:label.bounds.maxX+8,y:label.bounds.maxY+7},
      {side:"left",x:label.bounds.minX-8,y:label.bounds.minY-5},
      {side:"left",x:label.bounds.minX-8,y:label.bounds.maxY+7}
    ];
    let chosen=null;
    for(const candidate of candidates){
      const left=candidate.side==="right"?candidate.x:candidate.x-width;
      const box={left,right:left+width,top:candidate.y-height/2,bottom:candidate.y+height/2};
      if(box.left<4||box.right>w-4||box.top<4||box.bottom>h-4)continue;
      if(labelBoxes.some(existing=>boxesOverlap(box,existing)))continue;
      chosen={...candidate,box};break;
    }
    if(!chosen){
      const x=clamp(label.bounds.maxX+8,4,w-width-4),y=clamp(label.bounds.minY-5,8,h-8);
      chosen={side:"right",x,y,box:{left:x,right:x+width,top:y-height/2,bottom:y+height/2}};
    }
    labelBoxes.push(chosen.box);
    aircraftCtx.globalAlpha=label.alpha;
    aircraftCtx.strokeStyle=label.selected?"rgba(255,255,255,.45)":"rgba(139,233,255,.28)";aircraftCtx.lineWidth=.8;
    const anchorX=chosen.side==="right"?label.bounds.maxX:label.bounds.minX;
    const textEdgeX=chosen.x;
    aircraftCtx.beginPath();aircraftCtx.moveTo(anchorX,(label.bounds.minY+label.bounds.maxY)/2);aircraftCtx.lineTo(textEdgeX,chosen.y);aircraftCtx.stroke();
    aircraftCtx.fillStyle=label.selected?"#ffffff":"#dff8ff";aircraftCtx.textAlign=chosen.side==="right"?"left":"right";aircraftCtx.fillText(label.text,chosen.x,chosen.y);
    aircraftCtx.restore();
  }
}

function drawSelectionHalo(x,y,size){
  aircraftCtx.save();aircraftCtx.strokeStyle="rgba(255,255,255,.72)";aircraftCtx.lineWidth=1.1;aircraftCtx.setLineDash([3,4]);aircraftCtx.beginPath();aircraftCtx.arc(x,y,size*1.45+5,0,Math.PI*2);aircraftCtx.stroke();aircraftCtx.restore();
}

function drawPerspectiveAircraft(aircraft,state,w,h){
  if(state.azimuth===null||state.elevation===null)return null;
  const point=skyXY(state.azimuth,state.elevation,w,h);if(!point)return null;
  const[x,y]=point;
  const selected=typeof trackedObject!=="undefined"&&trackedObject?.kind==="aircraft"&&trackedObject.key===aircraft.icao24;
  const special=aircraft.display?.special||aircraft.military||aircraft.squawk_alert;
  const stroke=selected?"#ffffff":special?"#ffd166":"#8be9ff",glow=selected?"#ffffff":special?"#f59e0b":"#42d9ff";
  const size=modelSize(state.rangeKm,selected),camera=cameraBasis(state.azimuth,state.elevation),basis=aircraftBasis(state.heading,state.flightPathDeg,state.roll),kind=aircraftKind(aircraft),profile=aircraftProfile(aircraft);
  const coasting=aircraft?.position_state==="coasting"||aircraft?.continuity_state==="coasting";
  const alpha=selected?1:(coasting ? .62 : 1);
  let bounds;
  aircraftCtx.save();aircraftCtx.globalAlpha=alpha;
  if(kind==="helicopter"){
    drawHelicopterModel(basis,camera,size,x,y,stroke,glow,selected);bounds=projectedBounds(HELI_LANDMARKS,basis,camera,size,x,y);
  }else if(kind==="drone"){
    drawDroneModel(basis,camera,size,x,y,stroke,glow,selected);bounds=projectedBounds(DRONE_LANDMARKS,basis,camera,size,x,y);
  }else{
    const geometry=fixedWingGeometry(profile);drawFixedWingModel(geometry,basis,camera,size,x,y,stroke,glow,selected);bounds=projectedBounds(geometry.landmarks,basis,camera,size,x,y);
  }
  if(selected)drawSelectionHalo(x,y,size);
  aircraftCtx.restore();
  if(typeof labels!=="undefined"&&labels.aircraft){
    queuedLabels.push({text:(aircraft.display?.role?`${aircraft.display.role} · `:"")+(aircraft.callsign||aircraft.registration||aircraft.icao24||"AIR"),bounds,selected,alpha});
  }
  return{kind:"aircraft",item:aircraft,x,y,r:Math.max(15,size*1.35)};
}

function drawDotAircraft(aircraft,state,w,h){
  if(state.azimuth===null||state.elevation===null)return null;
  const point=skyXY(state.azimuth,state.elevation,w,h);if(!point)return null;
  const[x,y]=point;
  const selected=typeof trackedObject!=="undefined"&&trackedObject?.kind==="aircraft"&&trackedObject.key===aircraft.icao24;
  const special=aircraft.display?.special||aircraft.military||aircraft.squawk_alert;
  const stroke=selected?"#ffffff":special?"#ffd166":"#8be9ff",glow=selected?"#ffffff":special?"#f59e0b":"#42d9ff";
  const coasting=aircraft?.position_state==="coasting"||aircraft?.continuity_state==="coasting";
  const alpha=selected?1:(coasting ? .62 : 1);
  const radius=selected?6:4;
  aircraftCtx.save();
  aircraftCtx.globalAlpha=alpha;
  aircraftCtx.shadowBlur=selected?16:8;aircraftCtx.shadowColor=glow;
  aircraftCtx.fillStyle="rgba(3,7,13,.78)";aircraftCtx.strokeStyle=stroke;aircraftCtx.lineWidth=selected?2:1.35;
  aircraftCtx.beginPath();aircraftCtx.arc(x,y,radius,0,Math.PI*2);aircraftCtx.fill();aircraftCtx.stroke();
  aircraftCtx.restore();
  const bounds={minX:x-radius,maxX:x+radius,minY:y-radius,maxY:y+radius};
  if(typeof labels!=="undefined"&&labels.aircraft){
    queuedLabels.push({text:(aircraft.display?.role?`${aircraft.display.role} · `:"")+(aircraft.callsign||aircraft.registration||aircraft.icao24||"AIR"),bounds,selected,alpha});
  }
  return{kind:"aircraft",item:aircraft,x,y,r:15};
}

function ensureOverlaySize(){
  const w=skyCanvas.clientWidth||innerWidth,h=skyCanvas.clientHeight||innerHeight,dpr=Math.min(window.devicePixelRatio||1,2),pixelWidth=Math.max(1,Math.round(w*dpr)),pixelHeight=Math.max(1,Math.round(h*dpr));
  if(aircraftCanvas.width!==pixelWidth||aircraftCanvas.height!==pixelHeight){aircraftCanvas.width=pixelWidth;aircraftCanvas.height=pixelHeight}
  aircraftCtx.setTransform(dpr,0,0,dpr,0,0);return{w,h};
}

function clearOverlay(){const{w,h}=ensureOverlaySize();aircraftCtx.clearRect(0,0,w,h);aircraftHits=[];queuedLabels=[];labelBoxes=[]}

function drawPerspectiveLayer(){
  const{w,h}=ensureOverlaySize();aircraftCtx.clearRect(0,0,w,h);aircraftHits=[];queuedLabels=[];
  const nowMs=Date.now();
  const contacts=uniqueAircraftContacts(Array.isArray(skyAircraft)?skyAircraft:[]).map(aircraft=>({aircraft,state:interpolateTrack(aircraft,nowMs)})).filter(item=>item.state.azimuth!==null&&item.state.elevation!==null&&item.state.rangeKm<=MAX_RANGE_KM).sort((a,b)=>b.state.rangeKm-a.state.rangeKm);
  const drawAircraft=perspectiveEnabled()?drawPerspectiveAircraft:drawDotAircraft;
  for(const item of contacts){const target=drawAircraft(item.aircraft,item.state,w,h);if(target)aircraftHits.push(target)}
  drawAircraftLabels(w,h);
}

drawContacts=function(w,h){
  if(typeof layers==="undefined")return baseDrawContacts(w,h);
  const previous=layers.aircraft;
  try{layers.aircraft=false;return baseDrawContacts(w,h)}finally{layers.aircraft=previous}
};

function cleanupMotionEpochs(nowMs){
  if(nowMs-lastCleanup<5000)return;
  const active=new Set(uniqueAircraftContacts(Array.isArray(skyAircraft)?skyAircraft:[]).map((contact,index)=>aircraftIdentity(contact,index)));
  for(const[key,entry]of motionEpochs){if(!active.has(key)||nowMs-entry.lastSeenAt>60000){motionEpochs.delete(key);renderedStates.delete(key)}}
  lastCleanup=nowMs;
}

function animate(now){
  const reduced=window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
  const interval=reduced?REDUCED_MOTION_INTERVAL_MS:FRAME_INTERVAL_MS;
  if(now-lastDraw>=interval){
    if(!document.hidden&&typeof layers!=="undefined"&&layers.aircraft!==false&&Array.isArray(skyAircraft)&&skyAircraft.length)drawPerspectiveLayer();
    else clearOverlay();
    cleanupMotionEpochs(Date.now());
    lastDraw=now;
  }
  requestAnimationFrame(animate);
}

skyCanvas.addEventListener("click",event=>{
  if(typeof layers==="undefined"||layers.aircraft===false)return;
  if(typeof dragMoved!=="undefined"&&dragMoved)return;
  const rect=skyCanvas.getBoundingClientRect(),x=event.clientX-rect.left,y=event.clientY-rect.top;
  let best=null,bestD=Infinity;
  for(const target of aircraftHits){const d=Math.hypot(x-target.x,y-target.y);if(d<=target.r&&d<bestD){best=target;bestD=d}}
  if(!best)return;
  event.stopImmediatePropagation();if(typeof toggleTracking==="function")toggleTracking(best);drawSky();
},{capture:true});

const markerSelect=document.querySelector("#aircraft-marker-style");
if(markerSelect){
  const perspectiveOption=markerSelect.querySelector('option[value="silhouette"]');if(perspectiveOption)perspectiveOption.textContent="Perspective aircraft";
  markerSelect.addEventListener("change",()=>{clearOverlay();drawSky()});
  const help=markerSelect.closest(".radar-settings")?.querySelector("p.muted");
  if(help)help.textContent="Perspective aircraft use real heading, roll, turn rate and sky motion with readable view-dependent shapes, type-aware proportions, navigation lights and 0–50 mile depth scaling. Switch to dots for the lightweight simple view.";
}

window.NightAzimuthAircraftPerspective={active:true,modelSize,preparedTrack,interpolateTrack,cameraBasis,aircraftBasis,aircraftProfile,projectionFrame,snapshotCorrection,applySnapshotCorrection,uniqueAircraftContacts,aircraftIdentity,drawDotAircraft,drawPerspectiveLayer};
// Repaint the base sky once after taking ownership so a legacy silhouette already
// painted on the main canvas cannot remain behind the animated overlay.
requestAnimationFrame(()=>{if(typeof drawSky==="function")drawSky()});
requestAnimationFrame(animate);
})();