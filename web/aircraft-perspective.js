(()=>{
if(typeof drawContacts!=="function"||typeof drawSky!=="function"||typeof skyXY!=="function"||typeof ctx==="undefined")return;

const KM_PER_MILE=1.609344;
const MAX_RANGE_MILES=50;
const MAX_RANGE_KM=MAX_RANGE_MILES*KM_PER_MILE;
const MIN_MODEL_SIZE=7.5;
const MAX_MODEL_SIZE=24;
const ANIMATION_INTERVAL_MS=100;
const MAX_PREDICTION_SECONDS=15;
const DEG=Math.PI/180;
const baseDrawContacts=drawContacts;
const motionEpochs=new Map();
let lastAnimationFrame=0;
let lastCleanup=0;

const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));
const finite=value=>{const number=Number(value);return Number.isFinite(number)?number:null};
const shortestAngle=(from,to)=>((to-from+540)%360)-180;
const dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
const add=(a,b)=>[a[0]+b[0],a[1]+b[1],a[2]+b[2]];
const scale=(a,s)=>[a[0]*s,a[1]*s,a[2]*s];
const cross=(a,b)=>[
  a[1]*b[2]-a[2]*b[1],
  a[2]*b[0]-a[0]*b[2],
  a[0]*b[1]-a[1]*b[0]
];
function unit(vector){
  const length=Math.hypot(vector[0],vector[1],vector[2]);
  return length>1e-9?scale(vector,1/length):[0,0,0];
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
  if(/^(A3|B7|E1|E2|CRJ)|airbus|boeing|embraer|airliner|jet/.test(type+" "+description))return"jet";
  return"aircraft";
}

function modelSize(rangeKm,selected){
  const miles=clamp((finite(rangeKm)??MAX_RANGE_KM)/KM_PER_MILE,0,MAX_RANGE_MILES);
  const t=miles/MAX_RANGE_MILES;
  // Smoothstep preserves the exact end points while avoiding abrupt visual size
  // changes as a contact crosses the near/far ends of the 50-mile display.
  const eased=t*t*(3-2*t);
  return MAX_MODEL_SIZE-(MAX_MODEL_SIZE-MIN_MODEL_SIZE)*eased+(selected?2:0);
}

function contactFingerprint(aircraft){
  const track=Array.isArray(aircraft?.future_track)?aircraft.future_track:[];
  const first=track[0]||{};
  const last=track[track.length-1]||{};
  return [
    finite(aircraft?.azimuth_deg)?.toFixed(5),
    finite(aircraft?.elevation_deg)?.toFixed(5),
    finite(aircraft?.range_km)?.toFixed(4),
    finite(aircraft?.position_age_seconds)?.toFixed(2),
    finite(first.azimuth_deg)?.toFixed(5),
    finite(first.elevation_deg)?.toFixed(5),
    finite(last.azimuth_deg)?.toFixed(5),
    finite(last.elevation_deg)?.toFixed(5),
    finite(last.seconds_from_now)?.toFixed(2)
  ].join("|");
}

function motionEpoch(aircraft,nowMs){
  const key=String(aircraft?.icao24||"").toLowerCase();
  const fingerprint=contactFingerprint(aircraft);
  let entry=motionEpochs.get(key);
  if(!entry||entry.fingerprint!==fingerprint){
    entry={fingerprint,receivedAt:nowMs,lastSeenAt:nowMs};
    motionEpochs.set(key,entry);
  }else entry.lastSeenAt=nowMs;
  return entry;
}

function interpolateTrack(aircraft,nowMs){
  const entry=motionEpoch(aircraft,nowMs);
  const elapsed=clamp((nowMs-entry.receivedAt)/1000,0,MAX_PREDICTION_SECONDS);
  const source=Array.isArray(aircraft?.future_track)?aircraft.future_track:[];
  const points=source.map(point=>({
    seconds:finite(point?.seconds_from_now),
    azimuth:finite(point?.azimuth_deg),
    elevation:finite(point?.elevation_deg)
  })).filter(point=>point.seconds!==null&&point.azimuth!==null&&point.elevation!==null)
    .sort((a,b)=>a.seconds-b.seconds);

  let azimuth=finite(aircraft?.azimuth_deg);
  let elevation=finite(aircraft?.elevation_deg);
  if(points.length){
    if(elapsed<=points[0].seconds){
      azimuth=points[0].azimuth;elevation=points[0].elevation;
    }else if(elapsed>=points[points.length-1].seconds){
      azimuth=points[points.length-1].azimuth;elevation=points[points.length-1].elevation;
    }else{
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

  const trackDeg=finite(aircraft?.track_deg);
  const trueHeading=finite(aircraft?.true_heading_deg);
  const magneticHeading=finite(aircraft?.magnetic_heading_deg);
  const turnRate=finite(aircraft?.track_rate_deg_s);
  const baseHeading=trueHeading??trackDeg??magneticHeading??0;
  const heading=(baseHeading+(turnRate??0)*elapsed+360)%360;

  // The API does not provide pitch. Use the measured velocity vector instead:
  // vertical rate / ground speed gives a real flight-path angle, not invented
  // aircraft attitude. Keeping it bounded protects the drawing from bad fixes.
  const speed=finite(aircraft?.ground_speed_mps);
  const verticalRate=finite(aircraft?.vertical_rate_mps);
  const flightPathDeg=speed!==null&&speed>1&&verticalRate!==null
    ?clamp(Math.atan2(verticalRate,speed)/DEG,-20,20):0;

  // Smooth apparent depth between provider snapshots using measured radial
  // velocity. This does not change the true sky position used for identification.
  let rangeKm=finite(aircraft?.range_km)??MAX_RANGE_KM;
  if(trackDeg!==null&&speed!==null&&azimuth!==null){
    const horizontalRadial=speed*Math.cos(shortestAngle(azimuth,trackDeg)*DEG);
    const elevationRad=(elevation??0)*DEG;
    const verticalRadial=(verticalRate??0)*Math.sin(elevationRad);
    const slantRate=horizontalRadial*Math.cos(elevationRad)+verticalRadial;
    rangeKm=clamp(rangeKm+slantRate*elapsed/1000,0,MAX_RANGE_KM);
  }

  return{
    azimuth,elevation,rangeKm,heading,
    roll:clamp(finite(aircraft?.roll_deg)??0,-89,89),
    flightPathDeg,
    elapsed
  };
}

function cameraBasis(azimuthDeg,elevationDeg){
  const az=azimuthDeg*DEG,el=elevationDeg*DEG;
  const los=[Math.sin(az)*Math.cos(el),Math.cos(az)*Math.cos(el),Math.sin(el)];
  const right=[Math.cos(az),-Math.sin(az),0];
  const up=[-Math.sin(az)*Math.sin(el),-Math.cos(az)*Math.sin(el),Math.cos(el)];
  return{los,right,up};
}

function aircraftBasis(headingDeg,flightPathDeg,rollDeg){
  const heading=headingDeg*DEG,gamma=flightPathDeg*DEG;
  const forward=unit([
    Math.sin(heading)*Math.cos(gamma),
    Math.cos(heading)*Math.cos(gamma),
    Math.sin(gamma)
  ]);
  const worldUp=[0,0,1];
  const right0=unit(cross(forward,worldUp));
  const up0=unit(cross(right0,forward));
  const roll=rollDeg*DEG;
  // readsb/adsb.lol define negative roll as a left bank. Therefore positive
  // roll is right-wing-down: the aircraft right axis rotates toward -up.
  const right=add(scale(right0,Math.cos(roll)),scale(up0,-Math.sin(roll)));
  const up=add(scale(up0,Math.cos(roll)),scale(right0,Math.sin(roll)));
  return{forward,right:unit(right),up:unit(up)};
}

function projectLocal(local,basis,camera,size,originX,originY){
  const world=add(add(scale(basis.forward,local[0]),scale(basis.right,local[1])),scale(basis.up,local[2]));
  const sx=dot(world,camera.right);
  const sy=-dot(world,camera.up);
  const depth=dot(world,camera.los);
  const perspective=clamp(1/(1+depth*.12),.72,1.38);
  return[originX+sx*size*perspective,originY+sy*size*perspective,depth];
}

function pathFromLocal(points,basis,camera,size,x,y){
  const projected=points.map(point=>projectLocal(point,basis,camera,size,x,y));
  if(!projected.length)return projected;
  ctx.beginPath();ctx.moveTo(projected[0][0],projected[0][1]);
  for(let i=1;i<projected.length;i++)ctx.lineTo(projected[i][0],projected[i][1]);
  ctx.closePath();
  return projected;
}

function drawFixedWingModel(kind,basis,camera,size,x,y,stroke,glow,selected){
  const wing=kind==="glider"?1.18:kind==="light"?.72:.98;
  const bodyWidth=kind==="light"?.13:.105;
  const mainWing=[
    [.22,0,0],[-.08,wing,0],[-.30,wing*.82,0],[-.12,0,0],
    [-.30,-wing*.82,0],[-.08,-wing,0]
  ];
  const tailWing=[[-.62,0,0],[-.82,.42,0],[-.96,.36,0],[-.83,0,0],[-.96,-.36,0],[-.82,-.42,0]];
  const fuselage=[[1.22,0,0],[.38,bodyWidth,0],[-.93,bodyWidth*.62,0],[-1.08,0,0],[-.93,-bodyWidth*.62,0],[.38,-bodyWidth,0]];
  const fin=[[-.68,0,0],[-.92,0,.48],[-1.03,0,.08]];

  ctx.save();
  ctx.shadowColor=glow;ctx.shadowBlur=selected?18:8;
  ctx.lineJoin="round";ctx.lineCap="round";

  pathFromLocal(mainWing,basis,camera,size,x,y);
  ctx.fillStyle="rgba(105,216,239,.16)";ctx.strokeStyle=stroke;ctx.lineWidth=selected?1.9:1.15;ctx.fill();ctx.stroke();

  pathFromLocal(tailWing,basis,camera,size,x,y);
  ctx.fillStyle="rgba(105,216,239,.12)";ctx.fill();ctx.stroke();

  pathFromLocal(fin,basis,camera,size,x,y);
  ctx.fillStyle="rgba(160,235,250,.22)";ctx.fill();ctx.stroke();

  pathFromLocal(fuselage,basis,camera,size,x,y);
  ctx.fillStyle=selected?"rgba(235,252,255,.33)":"rgba(8,26,36,.82)";
  ctx.lineWidth=selected?2.2:1.45;ctx.fill();ctx.stroke();

  const nose=projectLocal([1.24,0,0],basis,camera,size,x,y);
  ctx.fillStyle=stroke;ctx.beginPath();ctx.arc(nose[0],nose[1],selected?1.8:1.2,0,Math.PI*2);ctx.fill();
  ctx.restore();
}

function drawHelicopterModel(basis,camera,size,x,y,stroke,glow,selected){
  ctx.save();ctx.strokeStyle=stroke;ctx.fillStyle="rgba(8,26,36,.82)";ctx.shadowColor=glow;ctx.shadowBlur=selected?18:8;ctx.lineWidth=selected?2:1.35;
  const body=[[.48,.16,0],[.62,0,0],[.30,-.18,0],[-.36,-.14,0],[-.54,0,0],[-.36,.14,0]];
  pathFromLocal(body,basis,camera,size,x,y);ctx.fill();ctx.stroke();
  const tailA=projectLocal([-.45,0,0],basis,camera,size,x,y),tailB=projectLocal([-1.05,0,0],basis,camera,size,x,y);
  ctx.beginPath();ctx.moveTo(tailA[0],tailA[1]);ctx.lineTo(tailB[0],tailB[1]);ctx.stroke();
  const rotorL=projectLocal([0,-1.05,.12],basis,camera,size,x,y),rotorR=projectLocal([0,1.05,.12],basis,camera,size,x,y);
  const rotorF=projectLocal([.82,0,.12],basis,camera,size,x,y),rotorB=projectLocal([-.82,0,.12],basis,camera,size,x,y);
  ctx.globalAlpha=.72;ctx.beginPath();ctx.moveTo(rotorL[0],rotorL[1]);ctx.lineTo(rotorR[0],rotorR[1]);ctx.moveTo(rotorF[0],rotorF[1]);ctx.lineTo(rotorB[0],rotorB[1]);ctx.stroke();ctx.restore();
}

function drawDroneModel(basis,camera,size,x,y,stroke,glow,selected){
  ctx.save();ctx.strokeStyle=stroke;ctx.fillStyle="rgba(8,26,36,.82)";ctx.shadowColor=glow;ctx.shadowBlur=selected?18:8;ctx.lineWidth=selected?2:1.3;
  const centre=projectLocal([0,0,0],basis,camera,size,x,y);
  for(const point of [[.55,.55,0],[.55,-.55,0],[-.55,.55,0],[-.55,-.55,0]]){
    const tip=projectLocal(point,basis,camera,size,x,y);ctx.beginPath();ctx.moveTo(centre[0],centre[1]);ctx.lineTo(tip[0],tip[1]);ctx.stroke();ctx.beginPath();ctx.arc(tip[0],tip[1],Math.max(1.5,size*.12),0,Math.PI*2);ctx.stroke();
  }
  ctx.beginPath();ctx.arc(centre[0],centre[1],Math.max(2,size*.16),0,Math.PI*2);ctx.fill();ctx.stroke();ctx.restore();
}

function drawSelectionHalo(x,y,size){
  ctx.save();ctx.strokeStyle="rgba(255,255,255,.72)";ctx.lineWidth=1.1;ctx.setLineDash([3,4]);
  ctx.beginPath();ctx.arc(x,y,size*1.45+5,0,Math.PI*2);ctx.stroke();ctx.restore();
}

function drawPerspectiveAircraft(aircraft,state,w,h){
  if(state.azimuth===null||state.elevation===null)return;
  const point=skyXY(state.azimuth,state.elevation,w,h);if(!point)return;
  const[x,y]=point;
  const selected=typeof trackedObject!=="undefined"&&trackedObject?.kind==="aircraft"&&trackedObject.key===aircraft.icao24;
  const special=aircraft.display?.special||aircraft.military||aircraft.squawk_alert;
  const stroke=selected?"#ffffff":special?"#ffd166":"#8be9ff";
  const glow=selected?"#ffffff":special?"#f59e0b":"#42d9ff";
  const size=modelSize(state.rangeKm,selected);
  const camera=cameraBasis(state.azimuth,state.elevation);
  const basis=aircraftBasis(state.heading,state.flightPathDeg,state.roll);
  const kind=aircraftKind(aircraft);

  if(kind==="helicopter")drawHelicopterModel(basis,camera,size,x,y,stroke,glow,selected);
  else if(kind==="drone")drawDroneModel(basis,camera,size,x,y,stroke,glow,selected);
  else drawFixedWingModel(kind,basis,camera,size,x,y,stroke,glow,selected);
  if(selected)drawSelectionHalo(x,y,size);

  ctx.save();ctx.fillStyle=selected?"#ffffff":"#dff8ff";ctx.textAlign="left";ctx.font=selected?"bold 10px ui-monospace,monospace":"10px ui-monospace,monospace";
  if(typeof labels!=="undefined"&&labels.aircraft)ctx.fillText((aircraft.display?.role?`${aircraft.display.role} · `:"")+(aircraft.callsign||aircraft.registration||aircraft.icao24||"AIR"),x+size*.72+7,y-size*.42);
  ctx.restore();
  if(typeof hit==="function")hit("aircraft",aircraft,[x,y],Math.max(15,size*1.35));
}

function drawPerspectiveLayer(w,h){
  const nowMs=Date.now();
  const contacts=(Array.isArray(skyAircraft)?skyAircraft:[]).map(aircraft=>({aircraft,state:interpolateTrack(aircraft,nowMs)}))
    .filter(item=>item.state.azimuth!==null&&item.state.elevation!==null&&item.state.rangeKm<=MAX_RANGE_KM)
    .sort((a,b)=>b.state.rangeKm-a.state.rangeKm);
  for(const item of contacts)drawPerspectiveAircraft(item.aircraft,item.state,w,h);
}

drawContacts=function(w,h){
  if(!perspectiveEnabled())return baseDrawContacts(w,h);
  const aircraftVisible=typeof layers!=="undefined"&&layers.aircraft!==false;
  if(!aircraftVisible)return baseDrawContacts(w,h);

  // Let the established renderer keep ownership of satellites, while preventing
  // its flat aircraft silhouettes from being painted underneath this layer.
  const previous=layers.aircraft;
  try{layers.aircraft=false;baseDrawContacts(w,h)}finally{layers.aircraft=previous}
  drawPerspectiveLayer(w,h);
};

function cleanupMotionEpochs(nowMs){
  if(nowMs-lastCleanup<5000)return;
  const active=new Set((Array.isArray(skyAircraft)?skyAircraft:[]).map(contact=>String(contact?.icao24||"").toLowerCase()));
  for(const[key,entry]of motionEpochs){if(!active.has(key)||nowMs-entry.lastSeenAt>60000)motionEpochs.delete(key)}
  lastCleanup=nowMs;
}

function animate(timestamp){
  if(!document.hidden&&perspectiveEnabled()&&typeof layers!=="undefined"&&layers.aircraft!==false&&Array.isArray(skyAircraft)&&skyAircraft.length){
    if(timestamp-lastAnimationFrame>=ANIMATION_INTERVAL_MS){drawSky();lastAnimationFrame=timestamp}
  }
  cleanupMotionEpochs(Date.now());
  requestAnimationFrame(animate);
}

const markerSelect=document.querySelector("#aircraft-marker-style");
if(markerSelect){
  const perspectiveOption=markerSelect.querySelector('option[value="silhouette"]');
  if(perspectiveOption)perspectiveOption.textContent="Perspective aircraft";
  markerSelect.addEventListener("change",()=>drawSky());
  const help=markerSelect.closest(".radar-settings")?.querySelector("p.muted");
  if(help)help.textContent="Perspective aircraft use reported heading, roll and turn rate, plus real sky motion and 0–50 mile depth scaling. Switch to dots for the lightweight simple view.";
}

window.NightAzimuthAircraftPerspective={
  modelSize,
  interpolateTrack,
  cameraBasis,
  aircraftBasis
};

requestAnimationFrame(animate);
})();
