(()=>{
const deviceSelect=document.querySelector("#camera-device");
const detectButton=document.querySelector("#camera-detect");
const startButton=document.querySelector("#camera-start");
const stopButton=document.querySelector("#camera-stop");
const captureButton=document.querySelector("#camera-capture-frame");
const profileInput=document.querySelector("#camera-profile");
const focalLengthInput=document.querySelector("#camera-focal-length");
const sensorWidthInput=document.querySelector("#camera-sensor-width");
const status=document.querySelector("#camera-status");
const previewShell=document.querySelector("#camera-preview-shell");
const preview=document.querySelector("#camera-preview");
const frameCanvas=document.querySelector("#camera-frame");
const frameStatus=document.querySelector("#camera-frame-status");
const settingsPanel=document.querySelector("#settings-panel");
const locationForm=document.querySelector("#settings-location-form");
if(!deviceSelect||!detectButton||!startButton||!stopButton||!captureButton||!profileInput||!focalLengthInput||!sensorWidthInput||!status||!previewShell||!preview||!frameCanvas||!frameStatus)return;

const solveActions=document.createElement("div");
solveActions.className="settings-actions";
const solveButton=document.createElement("button");
solveButton.id="camera-solve-frame";
solveButton.type="button";
solveButton.textContent="Plate solve captured frame";
solveButton.disabled=true;
solveActions.append(solveButton);
const solutionStatus=document.createElement("p");
solutionStatus.id="camera-solution-status";
solutionStatus.className="muted";
solutionStatus.setAttribute("role","status");
solutionStatus.setAttribute("aria-live","polite");
solutionStatus.textContent="Capture a star field to attempt a catalogue match.";
frameStatus.insertAdjacentElement("afterend",solveActions);
solveActions.insertAdjacentElement("afterend",solutionStatus);

const DEVICE_KEY="nightazimuth.cameraDeviceId";
const PROFILE_KEY="nightazimuth.cameraProfile";
const FOCAL_KEY="nightazimuth.cameraFocalLengthMm";
const SENSOR_KEY="nightazimuth.cameraSensorWidthMm";
const LATITUDE_KEY="nightazimuth.latitude";
const LONGITUDE_KEY="nightazimuth.longitude";
const CATALOGUE_CACHE_MS=15000;
const config=window.NIGHTAZIMUTH_CONFIG||{};
const apiBase=String(config.apiBaseUrl||"").replace(/\/$/,"");
let activeStream=null;
let lastFrame=null;
let solverLoadPromise=null;
let catalogueCache=null;
let solveGeneration=0;
let activeSolveCancel=null;

profileInput.value=localStorage.getItem(PROFILE_KEY)||"Sony A7S Gen 1";
focalLengthInput.value=localStorage.getItem(FOCAL_KEY)||"";
sensorWidthInput.value=localStorage.getItem(SENSOR_KEY)||"35.8";
const savedDeviceId=localStorage.getItem(DEVICE_KEY)||"";
if(savedDeviceId){
  const savedOption=document.createElement("option");
  savedOption.value=savedDeviceId;
  savedOption.textContent="Saved camera / capture device";
  savedOption.selected=true;
  deviceSelect.append(savedOption);
  status.textContent="Saved camera selection ready. Start camera or Detect cameras to refresh device names.";
}

function setStatus(message){status.textContent=message}
function cancelPendingSolve(){
  solveGeneration+=1;
  const cancel=activeSolveCancel;
  activeSolveCancel=null;
  if(cancel)cancel();
}
function invalidateSolution(message="Capture a star field to attempt a catalogue match.",{cancelPending=true}={}){
  if(cancelPending)cancelPendingSolve();
  delete window.NIGHTAZIMUTH_CAMERA_SOLUTION;
  solutionStatus.textContent=message;
}
function saveSettings(){
  if(deviceSelect.value)localStorage.setItem(DEVICE_KEY,deviceSelect.value);
  else localStorage.removeItem(DEVICE_KEY);
  localStorage.setItem(PROFILE_KEY,profileInput.value.trim()||"Sony A7S Gen 1");
  if(focalLengthInput.value)localStorage.setItem(FOCAL_KEY,focalLengthInput.value);
  else localStorage.removeItem(FOCAL_KEY);
  if(sensorWidthInput.value)localStorage.setItem(SENSOR_KEY,sensorWidthInput.value);
  else localStorage.removeItem(SENSOR_KEY);
}
function savedObserver(){
  const latitudeText=localStorage.getItem(LATITUDE_KEY);
  const longitudeText=localStorage.getItem(LONGITUDE_KEY);
  if(latitudeText==null||longitudeText==null||!latitudeText.trim()||!longitudeText.trim())return null;
  const latitude=Number(latitudeText),longitude=Number(longitudeText);
  if(!Number.isFinite(latitude)||latitude<-90||latitude>90||!Number.isFinite(longitude)||longitude<-180||longitude>180)return null;
  return{latitude,longitude};
}
function estimatedHorizontalFov(){
  const focal=Number(focalLengthInput.value),sensor=Number(sensorWidthInput.value);
  if(!(focal>0&&sensor>0))return null;
  return 2*Math.atan(sensor/(2*focal))*180/Math.PI;
}
function cameraDescription(){
  const track=activeStream?.getVideoTracks?.()[0],settings=track?.getSettings?.()||{};
  const resolution=settings.width&&settings.height?`${settings.width}×${settings.height}`:"live";
  const hfov=estimatedHorizontalFov();
  return `${track?.label||"Camera"} · ${resolution}${hfov?` · est. ${hfov.toFixed(1)}° HFOV`:""}`;
}
function updateSolveAvailability(){
  const enough=Boolean(lastFrame?.detection?.points?.length>=4);
  solveButton.disabled=!enough||!estimatedHorizontalFov();
  if(enough&&!estimatedHorizontalFov())solutionStatus.textContent="Enter the lens focal length so NightAzimuth can estimate camera field of view.";
}

async function populateDevices(){
  if(!navigator.mediaDevices?.enumerateDevices){setStatus("Camera discovery is not supported by this browser.");return}
  detectButton.disabled=true;
  setStatus("Checking available cameras…");
  let permissionStream=null;
  try{
    if(navigator.mediaDevices.getUserMedia){
      try{permissionStream=await navigator.mediaDevices.getUserMedia({video:true,audio:false})}catch{}
    }
    const devices=(await navigator.mediaDevices.enumerateDevices()).filter(device=>device.kind==="videoinput");
    const saved=localStorage.getItem(DEVICE_KEY)||"";
    deviceSelect.replaceChildren();
    const placeholder=document.createElement("option");
    placeholder.value="";
    placeholder.textContent=devices.length?"Select camera / capture device":"No camera devices found";
    deviceSelect.append(placeholder);
    let savedFound=false;
    devices.forEach((device,index)=>{
      const option=document.createElement("option");
      option.value=device.deviceId;
      option.textContent=device.label||`Camera ${index+1}`;
      if(device.deviceId===saved){option.selected=true;savedFound=true}
      deviceSelect.append(option);
    });
    if(saved&&!savedFound){
      const option=document.createElement("option");
      option.value=saved;
      option.textContent="Saved camera / capture device (not currently listed)";
      option.selected=true;
      deviceSelect.append(option);
    }
    setStatus(devices.length?`${devices.length} camera device${devices.length===1?"":"s"} found.`:"No camera devices were found.");
  }catch{
    setStatus("Unable to enumerate camera devices.");
  }finally{
    permissionStream?.getTracks().forEach(track=>track.stop());
    detectButton.disabled=false;
  }
}

function clearCapturedFrame({preserveSolution=false}={}){
  cancelPendingSolve();
  lastFrame=null;
  frameCanvas.hidden=true;
  frameStatus.textContent="No frame captured.";
  solveButton.disabled=true;
  if(!preserveSolution)invalidateSolution(undefined,{cancelPending:false});
}
function stopCamera({preserveSolution=false}={}){
  activeStream?.getTracks().forEach(track=>track.stop());
  activeStream=null;
  preview.srcObject=null;
  previewShell.hidden=true;
  startButton.disabled=false;
  stopButton.disabled=true;
  captureButton.disabled=true;
  clearCapturedFrame({preserveSolution});
}

async function startCamera(){
  if(!navigator.mediaDevices?.getUserMedia){setStatus("Camera access is not supported by this browser.");return}
  saveSettings();
  if(activeStream)stopCamera();
  else clearCapturedFrame();
  invalidateSolution("Camera started or restarted. Capture and solve a new frame before using alignment.",{cancelPending:false});
  startButton.disabled=true;
  setStatus("Starting camera…");
  try{
    const selected=deviceSelect.value;
    const preferredVideo=selected?{deviceId:{exact:selected},width:{ideal:1920},height:{ideal:1080}}:{width:{ideal:1920},height:{ideal:1080}};
    let usedFallback=false;
    try{
      activeStream=await navigator.mediaDevices.getUserMedia({video:preferredVideo,audio:false});
    }catch(error){
      const staleSelection=Boolean(selected)&&["NotFoundError","OverconstrainedError"].includes(String(error?.name||""));
      if(!staleSelection)throw error;
      localStorage.removeItem(DEVICE_KEY);
      deviceSelect.value="";
      usedFallback=true;
      setStatus("Saved camera is unavailable. Trying the default camera…");
      activeStream=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:1920},height:{ideal:1080}},audio:false});
    }
    preview.srcObject=activeStream;
    await preview.play();
    previewShell.hidden=false;
    startButton.disabled=true;
    stopButton.disabled=false;
    captureButton.disabled=false;
    setStatus(usedFallback?`${cameraDescription()} · saved selection unavailable; using default camera.`:cameraDescription());
  }catch(error){
    stopCamera();
    setStatus(error?.name==="NotAllowedError"?"Camera permission was denied.":"Unable to start the selected camera.");
  }
}

function detectBrightPoints(imageData,width,height){
  const image=imageData.data;
  const step=Math.max(2,Math.ceil(Math.max(width,height)/960));
  let sum=0,sumSq=0,count=0;
  for(let y=0;y<height;y+=step)for(let x=0;x<width;x+=step){
    const i=(y*width+x)*4,luma=image[i]*.2126+image[i+1]*.7152+image[i+2]*.0722;
    sum+=luma;sumSq+=luma*luma;count++;
  }
  const mean=sum/Math.max(1,count),variance=Math.max(0,sumSq/Math.max(1,count)-mean*mean),sigma=Math.sqrt(variance);
  const threshold=Math.min(252,Math.max(150,mean+Math.max(18,sigma*3.5)));
  const candidates=[];
  for(let y=step*2;y<height-step*2;y+=step){
    for(let x=step*2;x<width-step*2;x+=step){
      const i=(y*width+x)*4,luma=image[i]*.2126+image[i+1]*.7152+image[i+2]*.0722;
      if(luma<threshold)continue;
      let localMax=true;
      for(let oy=-step;oy<=step&&localMax;oy+=step)for(let ox=-step;ox<=step;ox+=step){
        if(!ox&&!oy)continue;
        const ni=((y+oy)*width+(x+ox))*4,n=image[ni]*.2126+image[ni+1]*.7152+image[ni+2]*.0722;
        if(n>luma){localMax=false;break}
      }
      if(localMax)candidates.push({x,y,luma});
    }
  }
  candidates.sort((a,b)=>b.luma-a.luma);
  const accepted=[];
  const minDistance=Math.max(6,step*3);
  for(const candidate of candidates){
    if(accepted.every(point=>Math.hypot(point.x-candidate.x,point.y-candidate.y)>=minDistance))accepted.push(candidate);
    if(accepted.length>=250)break;
  }
  return{points:accepted,threshold,mean};
}

function drawDetectionOverlay(context,detection){
  context.save();
  context.strokeStyle="rgba(118,255,184,.95)";
  context.lineWidth=1;
  for(const point of detection.points.slice(0,100)){
    context.beginPath();context.arc(point.x,point.y,5,0,Math.PI*2);context.stroke();
  }
  context.restore();
}
function captureFrame(){
  if(!activeStream||!preview.videoWidth||!preview.videoHeight){setStatus("Camera frame is not ready yet.");return}
  const maxWidth=1280,scale=Math.min(1,maxWidth/preview.videoWidth);
  const width=Math.max(1,Math.round(preview.videoWidth*scale)),height=Math.max(1,Math.round(preview.videoHeight*scale));
  frameCanvas.width=width;frameCanvas.height=height;
  const context=frameCanvas.getContext("2d",{willReadFrequently:true});
  context.drawImage(preview,0,0,width,height);
  // Read pixels once. The previous path allocated/read the full frame twice: once
  // for restoration and again for bright-point detection.
  const raw=context.getImageData(0,0,width,height),detection=detectBrightPoints(raw,width,height);
  lastFrame={width,height,raw,detection};
  invalidateSolution();
  drawDetectionOverlay(context,detection);
  frameCanvas.hidden=false;
  frameStatus.textContent=`${width}×${height} frame · ${detection.points.length} bright point candidate${detection.points.length===1?"":"s"} detected.`;
  solutionStatus.textContent=detection.points.length>=4?"Ready to compare the captured pattern with the live star catalogue.":"At least four distinct bright points are needed before a plate match can be attempted.";
  updateSolveAvailability();
}

function ensurePlateSolver(){
  if(window.NightAzimuthPlateSolver)return Promise.resolve(window.NightAzimuthPlateSolver);
  if(solverLoadPromise)return solverLoadPromise;
  solverLoadPromise=new Promise((resolve,reject)=>{
    const script=document.createElement("script");
    script.src="./camera-plate-solver.js?v=21.11.18";
    script.async=true;
    script.onload=()=>window.NightAzimuthPlateSolver?resolve(window.NightAzimuthPlateSolver):reject(new Error("Plate solver did not initialise"));
    script.onerror=()=>reject(new Error("Unable to load plate solver"));
    document.head.append(script);
  }).catch(error=>{
    // A transient asset/network failure must not permanently poison every later
    // solve attempt with the same rejected promise.
    solverLoadPromise=null;
    throw error;
  });
  return solverLoadPromise;
}
function currentCatalogueStars(latitude,longitude){
  try{
    if(typeof celestialSky==="undefined")return null;
    const sky=celestialSky,observer=sky?.observer||{};
    const calculated=Date.parse(sky?.calculated_at||"");
    const fresh=Number.isFinite(calculated)&&Math.abs(Date.now()-calculated)<=CATALOGUE_CACHE_MS;
    const sameObserver=Math.abs(Number(observer.latitude_deg)-latitude)<1e-6&&Math.abs(Number(observer.longitude_deg)-longitude)<1e-6;
    return fresh&&sameObserver&&Array.isArray(sky.stars)&&sky.stars.length>=4?sky.stars:null;
  }catch{return null}
}
async function fetchCatalogueStars(){
  const saved=savedObserver();
  if(!saved)throw new Error("Set and save a valid observer location first.");
  const {latitude,longitude}=saved;
  const current=currentCatalogueStars(latitude,longitude);
  if(current)return current;
  if(catalogueCache&&Date.now()-catalogueCache.fetchedAt<=CATALOGUE_CACHE_MS&&catalogueCache.latitude===latitude&&catalogueCache.longitude===longitude)return catalogueCache.stars;
  if(!apiBase)throw new Error("NightAzimuth API is not configured.");
  const target=new URL(`${apiBase}/api/v1/sky`);
  target.searchParams.set("latitude",String(latitude));
  target.searchParams.set("longitude",String(longitude));
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);
  try{
    const response=await fetch(target,{headers:{Accept:"application/json"},signal:controller.signal});
    if(!response.ok)throw new Error(`Sky catalogue request failed (${response.status}).`);
    const data=await response.json();
    const stars=Array.isArray(data.stars)?data.stars:[];
    catalogueCache={latitude,longitude,fetchedAt:Date.now(),stars};
    return stars;
  }finally{clearTimeout(timer)}
}
function solveWithWorker(payload){
  if(typeof Worker==="undefined")return ensurePlateSolver().then(solver=>solver.solve(payload));
  return new Promise((resolve,reject)=>{
    const worker=new Worker("./camera-plate-worker.js?v=21.11.18");
    const timer=setTimeout(()=>{
      if(activeSolveCancel===cancel)activeSolveCancel=null;
      worker.terminate();
      reject(new Error("Plate solver timed out."));
    },30000);
    let settled=false;
    const complete=()=>{
      if(settled)return false;
      settled=true;
      clearTimeout(timer);
      worker.terminate();
      if(activeSolveCancel===cancel)activeSolveCancel=null;
      return true;
    };
    const cancel=()=>{
      if(!complete())return;
      reject(new Error("Plate solve cancelled."));
    };
    activeSolveCancel=cancel;
    worker.onmessage=event=>{
      if(!complete())return;
      if(event.data?.error)reject(new Error(event.data.error));
      else resolve(event.data?.solution);
    };
    worker.onerror=()=>{if(complete())reject(new Error("Plate solver worker failed."))};
    worker.postMessage(payload);
  });
}
function drawSolution(solution){
  if(!lastFrame)return;
  const context=frameCanvas.getContext("2d",{willReadFrequently:true});
  context.putImageData(lastFrame.raw,0,0);
  context.save();
  context.font="12px ui-monospace,monospace";
  context.textAlign="left";
  for(const match of solution.matched||[]){
    const point=match.point,name=match.star?.name||`HIP ${match.star?.hip_id||"?"}`;
    context.strokeStyle="rgba(118,255,184,.98)";
    context.fillStyle="rgba(215,255,232,.98)";
    context.lineWidth=2;
    context.beginPath();context.arc(point.x,point.y,7,0,Math.PI*2);context.stroke();
    context.fillText(`${name} · ${match.separationDeg.toFixed(2)}°`,point.x+10,point.y-8);
  }
  context.restore();
}
async function solveCapturedFrame(){
  if(!lastFrame){solutionStatus.textContent="Capture a frame first.";return}
  const frame=lastFrame;
  const hfov=estimatedHorizontalFov();
  if(!hfov){solutionStatus.textContent="Enter the lens focal length before solving.";return}
  cancelPendingSolve();
  const generation=solveGeneration;
  solveButton.disabled=true;
  solutionStatus.textContent="Matching captured star pattern against the current sky catalogue…";
  try{
    const stars=await fetchCatalogueStars();
    if(generation!==solveGeneration||lastFrame!==frame)return;
    const solution=await solveWithWorker({points:frame.detection.points,stars,width:frame.width,height:frame.height,estimatedHfovDeg:hfov});
    if(generation!==solveGeneration||lastFrame!==frame)return;
    if(!solution)throw new Error("Plate solver returned no solution.");
    drawSolution(solution);
    if(solution.locked){
      window.NIGHTAZIMUTH_CAMERA_SOLUTION={...solution,solvedAt:new Date().toISOString()};
      window.dispatchEvent(new CustomEvent("nightazimuth:camera-solved",{detail:window.NIGHTAZIMUTH_CAMERA_SOLUTION}));
      solutionStatus.textContent=`LOCKED · ${solution.matches} star matches · az ${solution.azimuthDeg.toFixed(2)}° · el ${solution.elevationDeg.toFixed(2)}° · roll ${solution.rollDeg.toFixed(2)}° · HFOV ${solution.hfovDeg.toFixed(1)}° · RMS ${solution.rmsDeg.toFixed(2)}° · confidence ${Math.round(solution.confidence*100)}%.`;
    }else{
      invalidateSolution(`NOT LOCKED · ${solution.matches||0} match${solution.matches===1?"":"es"}. ${solution.reason||"The star pattern is not distinctive enough yet."}`,{cancelPending:false});
    }
  }catch(error){
    if(generation!==solveGeneration||lastFrame!==frame)return;
    invalidateSolution(error?.name==="AbortError"?"Sky catalogue request timed out.":String(error?.message||"Unable to plate solve this frame."),{cancelPending:false});
  }finally{
    if(generation===solveGeneration)updateSolveAvailability();
  }
}

function cameraGeometryChanged(){
  saveSettings();
  catalogueCache=null;
  invalidateSolution("Camera/lens settings changed. Capture and solve a new frame.");
  updateSolveAvailability();
  if(activeStream)setStatus(cameraDescription());
}

detectButton.addEventListener("click",populateDevices);
startButton.addEventListener("click",startCamera);
stopButton.addEventListener("click",()=>{stopCamera({preserveSolution:true});setStatus("Camera stopped. Last plate solution retained.")});
captureButton.addEventListener("click",captureFrame);
solveButton.addEventListener("click",solveCapturedFrame);
deviceSelect.addEventListener("change",()=>{saveSettings();catalogueCache=null;invalidateSolution("Camera selection changed. Capture and solve a new frame.");if(activeStream){stopCamera();setStatus("Camera selection changed. Start camera to apply.")}});
profileInput.addEventListener("change",cameraGeometryChanged);
focalLengthInput.addEventListener("change",cameraGeometryChanged);
sensorWidthInput.addEventListener("change",cameraGeometryChanged);
if(locationForm)locationForm.addEventListener("submit",()=>{catalogueCache=null;invalidateSolution("Observer location changed. Capture and solve a new frame.")});
window.addEventListener("beforeunload",()=>stopCamera({preserveSolution:true}));
if(settingsPanel)new MutationObserver(()=>{if(settingsPanel.hidden&&activeStream)stopCamera({preserveSolution:true})}).observe(settingsPanel,{attributes:true,attributeFilter:["hidden"]});
})();
