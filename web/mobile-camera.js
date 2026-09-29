(()=>{
const details=document.querySelector("#camera-settings-details");
const deviceSelect=document.querySelector("#camera-device");
const startButton=document.querySelector("#camera-start");
const captureButton=document.querySelector("#camera-capture-frame");
const preview=document.querySelector("#camera-preview");
const previewShell=document.querySelector("#camera-preview-shell");
const profileInput=document.querySelector("#camera-profile");
const focalLengthInput=document.querySelector("#camera-focal-length");
const sensorWidthInput=document.querySelector("#camera-sensor-width");
const solutionStatus=document.querySelector("#camera-solution-status");
const cameraStatus=document.querySelector("#camera-status");
if(!details||!deviceSelect||!startButton||!captureButton||!preview||!previewShell||!profileInput||!focalLengthInput||!sensorWidthInput||!cameraStatus)return;

const MOBILE_HFOV_KEY="nightazimuth.mobileCameraHfovDeg";
const STABLE_RATE_DEG_S=1.5;
const SETTLING_RATE_DEG_S=5;
const LOCK_INVALIDATION_RATE_DEG_S=5;
const STABLE_DWELL_MS=750;
const STABLE_WAIT_MS=8000;
const DEFAULT_MOBILE_HFOV_DEG=65;
const likelyMobile=Boolean(
  navigator.userAgentData?.mobile||
  /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent||"")||
  ((navigator.maxTouchPoints||0)>=2&&matchMedia?.("(pointer: coarse)")?.matches)
);

const panel=document.createElement("section");
panel.id="mobile-camera-settings";
panel.className="radar-settings mobile-camera-settings";
panel.hidden=!likelyMobile;
const heading=document.createElement("h4");
heading.textContent="Mobile handheld camera";
const intro=document.createElement("p");
intro.className="muted";
intro.textContent="Rear-camera mode for phones and tablets. NightAzimuth waits for the handset to become steady before capturing a plate-solve frame; motion sensors are used only after you explicitly enable handheld tracking.";
const fovLabel=document.createElement("label");
fovLabel.htmlFor="mobile-camera-hfov";
fovLabel.textContent="Estimated rear-camera horizontal FOV";
const fovInput=document.createElement("input");
fovInput.id="mobile-camera-hfov";
fovInput.type="number";
fovInput.min="30";
fovInput.max="130";
fovInput.step="1";
fovInput.value=localStorage.getItem(MOBILE_HFOV_KEY)||String(DEFAULT_MOBILE_HFOV_DEG);
fovLabel.append(fovInput);
const actions=document.createElement("div");
actions.className="settings-actions camera-actions";
const startRearButton=document.createElement("button");
startRearButton.id="mobile-camera-start-rear";
startRearButton.type="button";
startRearButton.textContent="Start rear camera";
const motionButton=document.createElement("button");
motionButton.id="mobile-camera-enable-motion";
motionButton.type="button";
motionButton.textContent="Enable handheld tracking";
const stableSolveButton=document.createElement("button");
stableSolveButton.id="mobile-camera-stable-solve";
stableSolveButton.type="button";
stableSolveButton.textContent="Capture & solve when steady";
stableSolveButton.disabled=true;
actions.append(startRearButton,motionButton,stableSolveButton);
const motionStatus=document.createElement("p");
motionStatus.id="mobile-camera-motion-status";
motionStatus.className="muted";
motionStatus.setAttribute("role","status");
motionStatus.setAttribute("aria-live","polite");
motionStatus.textContent=likelyMobile?"HANDHELD READY · rear camera not started":"Handheld mode is available on mobile browsers.";
panel.append(heading,intro,fovLabel,actions,motionStatus);
cameraStatus.insertAdjacentElement("afterend",panel);

let handheldSession=false;
let motionEnabled=false;
let motionRate=null;
let smoothedMotionRate=null;
let stableSince=0;
let lastOrientation=null;
let lastOrientationAt=0;
let latestOrientation=null;
let lastInvalidatedAt=0;

const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const wrapDelta=(a,b)=>((a-b+540)%360)-180;
function dispatchChange(input){input.dispatchEvent(new Event("change",{bubbles:true}))}
function currentFov(){
  const value=Number(fovInput.value);
  return Number.isFinite(value)&&value>=30&&value<=130?value:DEFAULT_MOBILE_HFOV_DEG;
}
function applyEquivalentFov(){
  const hfov=currentFov();
  localStorage.setItem(MOBILE_HFOV_KEY,String(hfov));
  const sensor=35.8;
  const focal=sensor/(2*Math.tan(hfov*Math.PI/360));
  profileInput.value="Mobile rear camera";
  sensorWidthInput.value=String(sensor);
  focalLengthInput.value=focal.toFixed(2);
  dispatchChange(profileInput);
  dispatchChange(sensorWidthInput);
  dispatchChange(focalLengthInput);
}
function motionState(){
  if(!motionEnabled)return"SENSORS OFF";
  if(!Number.isFinite(smoothedMotionRate))return"SEARCHING";
  if(smoothedMotionRate<=STABLE_RATE_DEG_S)return"STABLE";
  if(smoothedMotionRate<=SETTLING_RATE_DEG_S)return"STABILISING";
  return"MOVING";
}
function publishHandheldState(){
  window.NIGHTAZIMUTH_HANDHELD_STATE={
    mobileDetected:likelyMobile,
    enabled:motionEnabled,
    state:motionState(),
    motionDegPerSec:Number.isFinite(smoothedMotionRate)?smoothedMotionRate:null,
    stableForMs:stableSince?Math.max(0,Date.now()-stableSince):0,
    orientation:latestOrientation,
    rearCameraSession:handheldSession,
    updatedAt:new Date().toISOString()
  };
}
function updateMotionStatus(prefix=""){
  const state=motionState();
  const rate=Number.isFinite(smoothedMotionRate)?` · ${smoothedMotionRate.toFixed(1)}°/s`:"";
  const lock=window.NIGHTAZIMUTH_CAMERA_SOLUTION?.handheld?" · PLATE LOCKED":"";
  motionStatus.textContent=`${prefix}${state}${rate}${lock}`;
  publishHandheldState();
}
function invalidateMovedHandheldSolution(){
  const solution=window.NIGHTAZIMUTH_CAMERA_SOLUTION;
  if(!solution?.handheld||!Number.isFinite(smoothedMotionRate)||smoothedMotionRate<=LOCK_INVALIDATION_RATE_DEG_S)return;
  const now=Date.now();
  if(now-lastInvalidatedAt<500)return;
  lastInvalidatedAt=now;
  delete window.NIGHTAZIMUTH_CAMERA_SOLUTION;
  if(solutionStatus)solutionStatus.textContent="Phone moved after the plate solve. Hold steady and re-lock before using camera alignment.";
  updateMotionStatus("RE-LOCK REQUIRED · ");
}
function acceptMotionRate(rate){
  if(!Number.isFinite(rate)||rate<0)return;
  motionRate=rate;
  smoothedMotionRate=smoothedMotionRate==null?rate:smoothedMotionRate*.72+rate*.28;
  if(smoothedMotionRate<=STABLE_RATE_DEG_S){
    if(!stableSince)stableSince=Date.now();
  }else stableSince=0;
  updateMotionStatus();
  invalidateMovedHandheldSolution();
}
function onDeviceMotion(event){
  const rotation=event.rotationRate;
  if(!rotation)return;
  const values=[rotation.alpha,rotation.beta,rotation.gamma].map(value=>Number(value)).filter(Number.isFinite);
  if(!values.length)return;
  acceptMotionRate(Math.hypot(...values));
}
function onDeviceOrientation(event){
  const now=performance.now();
  const orientation={alpha:Number(event.alpha),beta:Number(event.beta),gamma:Number(event.gamma),absolute:Boolean(event.absolute)};
  latestOrientation=orientation;
  if(lastOrientation&&lastOrientationAt&&[orientation.alpha,orientation.beta,orientation.gamma,lastOrientation.alpha,lastOrientation.beta,lastOrientation.gamma].every(Number.isFinite)){
    const seconds=Math.max(.016,(now-lastOrientationAt)/1000);
    const delta=Math.hypot(
      wrapDelta(orientation.alpha,lastOrientation.alpha),
      orientation.beta-lastOrientation.beta,
      wrapDelta(orientation.gamma,lastOrientation.gamma)
    );
    // DeviceMotion rotationRate is preferred. DeviceOrientation provides a
    // cross-browser fallback where rotationRate is unavailable or withheld.
    if(!Number.isFinite(motionRate))acceptMotionRate(delta/seconds);
  }
  lastOrientation=orientation;
  lastOrientationAt=now;
  publishHandheldState();
}
async function requestSensorPermission(){
  const requests=[];
  const motionCtor=window.DeviceMotionEvent;
  const orientationCtor=window.DeviceOrientationEvent;
  try{
    if(typeof motionCtor?.requestPermission==="function")requests.push(motionCtor.requestPermission());
    if(typeof orientationCtor?.requestPermission==="function")requests.push(orientationCtor.requestPermission());
    const results=await Promise.all(requests);
    if(results.some(result=>result!=="granted"))return false;
    return Boolean(motionCtor||orientationCtor);
  }catch{return false}
}
async function enableHandheldTracking(){
  if(motionEnabled)return true;
  motionButton.disabled=true;
  motionStatus.textContent="Requesting motion-sensor access…";
  const available=await requestSensorPermission();
  if(!available){
    motionStatus.textContent="Motion sensors are unavailable or permission was denied. You can still use manual Capture test frame.";
    motionButton.disabled=false;
    return false;
  }
  window.addEventListener("devicemotion",onDeviceMotion,{passive:true});
  window.addEventListener("deviceorientation",onDeviceOrientation,{passive:true});
  motionEnabled=true;
  motionButton.textContent="Handheld tracking enabled";
  motionButton.disabled=true;
  updateMotionStatus();
  return true;
}
function ensureDeviceOption(deviceId,label){
  if(!deviceId)return false;
  let option=Array.from(deviceSelect.options).find(item=>item.value===deviceId);
  if(!option){
    option=document.createElement("option");
    option.value=deviceId;
    option.textContent=label||"Mobile rear camera";
    deviceSelect.append(option);
  }
  deviceSelect.value=deviceId;
  dispatchChange(deviceSelect);
  return true;
}
async function startRearCamera(){
  if(!navigator.mediaDevices?.getUserMedia){motionStatus.textContent="Rear-camera access is not supported by this browser.";return}
  startRearButton.disabled=true;
  motionStatus.textContent="Requesting the rear-facing camera…";
  applyEquivalentFov();
  let probe=null;
  try{
    probe=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:"environment"},width:{ideal:1920},height:{ideal:1080}},audio:false});
    const track=probe.getVideoTracks()[0];
    const settings=track?.getSettings?.()||{};
    const label=track?.label||"Mobile rear camera";
    const selected=ensureDeviceOption(settings.deviceId,label);
    probe.getTracks().forEach(item=>item.stop());
    probe=null;
    if(!selected){
      motionStatus.textContent="Rear camera was found, but this browser did not expose its device ID. Use Detect cameras and choose the rear camera manually.";
      return;
    }
    handheldSession=true;
    motionStatus.textContent="Rear camera selected. Starting NightAzimuth camera preview…";
    startButton.click();
  }catch(error){
    probe?.getTracks().forEach(item=>item.stop());
    motionStatus.textContent=error?.name==="NotAllowedError"?"Camera permission was denied.":"Unable to start the rear-facing camera.";
  }finally{startRearButton.disabled=false}
}
async function waitUntilStable(){
  const sensors=await enableHandheldTracking();
  if(!sensors){
    motionStatus.textContent="Motion sensing is unavailable. Hold the phone steady; capturing in 1 second…";
    await delay(1000);
    return true;
  }
  const deadline=Date.now()+STABLE_WAIT_MS;
  stableSince=0;
  while(Date.now()<deadline){
    if(stableSince&&Date.now()-stableSince>=STABLE_DWELL_MS)return true;
    updateMotionStatus("WAITING · ");
    await delay(100);
  }
  return false;
}
async function captureAndSolveWhenStable(){
  if(!handheldSession||!preview.srcObject||previewShell.hidden){motionStatus.textContent="Start the mobile rear camera first.";return}
  stableSolveButton.disabled=true;
  const stable=await waitUntilStable();
  if(!stable){
    motionStatus.textContent="STILL MOVING · could not get a steady 0.75 second window. Try again or rest the phone against something.";
    stableSolveButton.disabled=false;
    return;
  }
  motionStatus.textContent="STABLE · capturing star field…";
  captureButton.click();
  await delay(0);
  const solveButton=document.querySelector("#camera-solve-frame");
  if(!solveButton||solveButton.disabled){
    motionStatus.textContent="STABLE · frame captured, but there are not enough star candidates to plate solve yet.";
    stableSolveButton.disabled=false;
    return;
  }
  motionStatus.textContent="STABLE · plate solving…";
  solveButton.click();
  stableSolveButton.disabled=false;
}
function updatePreviewAvailability(){
  stableSolveButton.disabled=!(handheldSession&&preview.srcObject&&!previewShell.hidden);
}

fovInput.addEventListener("change",()=>{applyEquivalentFov();if(window.NIGHTAZIMUTH_CAMERA_SOLUTION?.handheld){delete window.NIGHTAZIMUTH_CAMERA_SOLUTION;if(solutionStatus)solutionStatus.textContent="Mobile camera FOV estimate changed. Capture and solve again."}});
startRearButton.addEventListener("click",startRearCamera);
motionButton.addEventListener("click",enableHandheldTracking);
stableSolveButton.addEventListener("click",captureAndSolveWhenStable);
preview.addEventListener("playing",()=>{updatePreviewAvailability();updateMotionStatus("CAMERA READY · ")});
new MutationObserver(updatePreviewAvailability).observe(previewShell,{attributes:true,attributeFilter:["hidden"]});
window.addEventListener("nightazimuth:camera-solved",event=>{
  if(!handheldSession||!event.detail)return;
  event.detail.handheld=true;
  event.detail.motionDegPerSec=Number.isFinite(smoothedMotionRate)?smoothedMotionRate:null;
  event.detail.orientationSnapshot=latestOrientation;
  event.detail.mobileHfovEstimateDeg=currentFov();
  updateMotionStatus("LOCKED · ");
});
window.addEventListener("beforeunload",()=>{
  if(motionEnabled){
    window.removeEventListener("devicemotion",onDeviceMotion);
    window.removeEventListener("deviceorientation",onDeviceOrientation);
  }
});
publishHandheldState();
})();
