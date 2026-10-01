(()=>{
const canvasEl=document.querySelector("#sky-canvas");
if(!canvasEl||typeof skyXY!=="function"||typeof verticalFovFor!=="function"||typeof drawSky!=="function")return;

const MODE_KEY="nightazimuth.skyDepthMode";
const FLAT_SKY_XY=skyXY;
const baseDrawSky=drawSky;
const DEG=Math.PI/180;

function depthMode(){
  const value=localStorage.getItem(MODE_KEY);
  return value==="flat"||value==="enhanced"?value:"natural";
}

function stereographicCoordinates(azimuthOffsetDeg,elevationDeg,centreElevationDeg){
  const offset=azimuthOffsetDeg*DEG;
  const elevation=elevationDeg*DEG;
  const centre=centreElevationDeg*DEG;
  const side=Math.cos(elevation)*Math.sin(offset);
  const forward=Math.cos(elevation)*Math.cos(offset);
  const up=Math.sin(elevation);
  const cameraX=side;
  const cameraY=-forward*Math.sin(centre)+up*Math.cos(centre);
  const cameraZ=forward*Math.cos(centre)+up*Math.sin(centre);
  const denominator=Math.max(1e-9,1+cameraZ);
  return [2*cameraX/denominator,2*cameraY/denominator];
}

function perceptualXY(az,el,w,h){
  const base=FLAT_SKY_XY(az,el,w,h);
  if(!base||depthMode()==="flat")return base;

  const horizontalFov=Math.max(5,Math.min(175,Number(fov)||120));
  const verticalFov=Math.max(1,Math.min(90,Number(verticalFovFor(w,h))||45));
  const centreElevation=Number(elevationCentre)||verticalFov/2;
  const off=angularDifference(Number(az),Number(facing));
  const elevation=Number(el);
  if(!Number.isFinite(off)||!Number.isFinite(elevation))return null;
  if(Math.abs(off)>horizontalFov/2||Math.abs(elevation-centreElevation)>verticalFov/2||elevation<0||elevation>90)return null;

  const minElevation=Math.max(0,centreElevation-verticalFov/2);
  const maxElevation=Math.min(90,centreElevation+verticalFov/2);
  const [rawX,rawY]=stereographicCoordinates(off,elevation,centreElevation);
  const [edgeX]=stereographicCoordinates(horizontalFov/2,centreElevation,centreElevation);
  const [,topY]=stereographicCoordinates(0,maxElevation,centreElevation);
  const [,bottomY]=stereographicCoordinates(0,minElevation,centreElevation);
  const xScale=Math.max(Math.abs(edgeX),1e-9);
  const verticalSpan=Math.max(topY-bottomY,1e-9);
  let xFraction=.5+.5*rawX/xScale;
  let yFraction=1-(rawY-bottomY)/verticalSpan;
  xFraction=Math.max(-.15,Math.min(1.15,xFraction));
  yFraction=Math.max(-.15,Math.min(1.15,yFraction));

  const usableHeight=verticalFov*Math.max(w,1)/horizontalFov;
  let x=w*.06+xFraction*w*.88;
  let y=usableHeight*(.05+yFraction*.9);

  if(depthMode()==="enhanced"){
    const centreX=w*.5,centreY=usableHeight*.5;
    x=centreX+(x-centreX)*1.06;
    y=centreY+(y-centreY)*1.045;
  }
  return [x,y];
}

function depthMetrics(az,el,rangeKm=null){
  const w=canvasEl.clientWidth||innerWidth;
  const h=canvasEl.clientHeight||innerHeight;
  const point=perceptualXY(az,el,w,h);
  if(!point)return null;
  const verticalFov=verticalFovFor(w,h);
  const usableHeight=verticalFov*Math.max(w,1)/Math.max(Number(fov)||120,1);
  const dx=(point[0]-w*.5)/(w*.5);
  const dy=(point[1]-usableHeight*.5)/(Math.max(usableHeight,1)*.5);
  const eccentricity=Math.min(1,Math.hypot(dx,dy));
  const elevation=Math.max(0,Math.min(90,Number(el)||0));
  const horizonProximity=Math.max(0,1-elevation/28);
  const range=Number(rangeKm);
  const rangeNearness=Number.isFinite(range)?1-Math.min(1,Math.log1p(Math.max(0,range))/Math.log1p(2000)):null;
  return {point,eccentricity,horizonProximity,rangeNearness};
}

skyXY=perceptualXY;

function drawAtmosphericDepth(){
  if(depthMode()==="flat")return;
  const w=canvasEl.clientWidth||innerWidth;
  const h=canvasEl.clientHeight||innerHeight;
  if(!(w>0&&h>0))return;
  const intensity=depthMode()==="enhanced"?1.35:1;
  const samples=[];
  for(let step=0;step<=48;step++){
    const off=-Number(fov)/2+(Number(fov)*step/48);
    const point=perceptualXY((Number(facing)+off+360)%360,0,w,h);
    if(point)samples.push(point);
  }
  if(samples.length>1){
    ctx.save();
    const topShift=depthMode()==="enhanced"?82:62;
    const gradient=ctx.createLinearGradient(0,Math.min(...samples.map(p=>p[1]))-topShift,0,Math.max(...samples.map(p=>p[1]))+18);
    gradient.addColorStop(0,"rgba(24,74,108,0)");
    gradient.addColorStop(.58,`rgba(43,104,137,${(.035*intensity).toFixed(3)})`);
    gradient.addColorStop(1,`rgba(92,153,174,${(.13*intensity).toFixed(3)})`);
    ctx.fillStyle=gradient;
    ctx.beginPath();
    ctx.moveTo(samples[0][0],samples[0][1]-topShift);
    for(const [x,y] of samples)ctx.lineTo(x,y-topShift);
    for(let i=samples.length-1;i>=0;i--){const [x,y]=samples[i];ctx.lineTo(x,y+24)}
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }

  ctx.save();
  const vignette=ctx.createRadialGradient(w*.5,h*.42,Math.min(w,h)*.22,w*.5,h*.46,Math.max(w,h)*.7);
  vignette.addColorStop(0,"rgba(0,0,0,0)");
  vignette.addColorStop(.7,"rgba(0,0,0,0)");
  vignette.addColorStop(1,`rgba(0,0,0,${depthMode()==="enhanced"?.16:.10})`);
  ctx.fillStyle=vignette;
  ctx.fillRect(0,0,w,h);
  ctx.restore();
}

drawSky=function(){
  baseDrawSky();
  drawAtmosphericDepth();
};

function installSetting(){
  const viewControls=document.querySelector(".settings-view-controls");
  if(!viewControls||document.querySelector("#sky-depth-mode"))return;
  const label=document.createElement("label");
  label.htmlFor="sky-depth-mode";
  label.textContent="Live Sky depth";
  const select=document.createElement("select");
  select.id="sky-depth-mode";
  select.innerHTML='<option value="natural">Natural</option><option value="enhanced">Enhanced</option><option value="flat">Flat</option>';
  select.value=depthMode();
  label.append(select);
  const note=document.createElement("p");
  note.id="sky-depth-help";
  note.className="muted";
  note.textContent="Natural uses a spherical observer view with subtle horizon atmosphere. Enhanced strengthens the depth cues. Flat restores the legacy chart-like projection.";
  viewControls.append(label,note);
  select.addEventListener("change",()=>{
    const value=select.value==="enhanced"||select.value==="flat"?select.value:"natural";
    localStorage.setItem(MODE_KEY,value);
    drawSky();
  });
}

window.NightAzimuthDepth={
  get mode(){return depthMode()},
  metrics:depthMetrics,
  project:perceptualXY
};

installSetting();
requestAnimationFrame(()=>drawSky());
})();
