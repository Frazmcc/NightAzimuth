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
if(!deviceSelect||!detectButton||!startButton||!stopButton||!captureButton||!profileInput||!focalLengthInput||!sensorWidthInput||!status||!previewShell||!preview||!frameCanvas||!frameStatus)return;

const DEVICE_KEY="nightazimuth.cameraDeviceId";
const PROFILE_KEY="nightazimuth.cameraProfile";
const FOCAL_KEY="nightazimuth.cameraFocalLengthMm";
const SENSOR_KEY="nightazimuth.cameraSensorWidthMm";
let activeStream=null;

profileInput.value=localStorage.getItem(PROFILE_KEY)||"Sony A7S Gen 1";
focalLengthInput.value=localStorage.getItem(FOCAL_KEY)||"";
sensorWidthInput.value=localStorage.getItem(SENSOR_KEY)||"35.8";

function setStatus(message){status.textContent=message}
function saveSettings(){
  if(deviceSelect.value)localStorage.setItem(DEVICE_KEY,deviceSelect.value);
  else localStorage.removeItem(DEVICE_KEY);
  localStorage.setItem(PROFILE_KEY,profileInput.value.trim()||"Sony A7S Gen 1");
  if(focalLengthInput.value)localStorage.setItem(FOCAL_KEY,focalLengthInput.value);
  else localStorage.removeItem(FOCAL_KEY);
  if(sensorWidthInput.value)localStorage.setItem(SENSOR_KEY,sensorWidthInput.value);
  else localStorage.removeItem(SENSOR_KEY);
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

async function populateDevices(){
  if(!navigator.mediaDevices?.enumerateDevices){setStatus("Camera discovery is not supported by this browser.");return}
  detectButton.disabled=true;
  setStatus("Checking available cameras…");
  let permissionStream=null;
  try{
    // Request access only after the user explicitly clicks Detect cameras so
    // NightAzimuth never prompts for camera permission on page load.
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
    devices.forEach((device,index)=>{
      const option=document.createElement("option");
      option.value=device.deviceId;
      option.textContent=device.label||`Camera ${index+1}`;
      if(device.deviceId===saved)option.selected=true;
      deviceSelect.append(option);
    });
    setStatus(devices.length?`${devices.length} camera device${devices.length===1?"":"s"} found.`:"No camera devices were found.");
  }catch{
    setStatus("Unable to enumerate camera devices.");
  }finally{
    permissionStream?.getTracks().forEach(track=>track.stop());
    detectButton.disabled=false;
  }
}

function stopCamera(){
  activeStream?.getTracks().forEach(track=>track.stop());
  activeStream=null;
  preview.srcObject=null;
  previewShell.hidden=true;
  startButton.disabled=false;
  stopButton.disabled=true;
  captureButton.disabled=true;
  frameCanvas.hidden=true;
  frameStatus.textContent="No frame captured.";
}

async function startCamera(){
  if(!navigator.mediaDevices?.getUserMedia){setStatus("Camera access is not supported by this browser.");return}
  saveSettings();
  startButton.disabled=true;
  setStatus("Starting camera…");
  try{
    if(activeStream)stopCamera();
    const selected=deviceSelect.value;
    const video=selected?{deviceId:{exact:selected},width:{ideal:1920},height:{ideal:1080}}:{width:{ideal:1920},height:{ideal:1080}};
    activeStream=await navigator.mediaDevices.getUserMedia({video,audio:false});
    preview.srcObject=activeStream;
    await preview.play();
    previewShell.hidden=false;
    startButton.disabled=true;
    stopButton.disabled=false;
    captureButton.disabled=false;
    setStatus(cameraDescription());
  }catch(error){
    stopCamera();
    setStatus(error?.name==="NotAllowedError"?"Camera permission was denied.":"Unable to start the selected camera.");
  }
}

function detectBrightPoints(context,width,height){
  const image=context.getImageData(0,0,width,height).data;
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

function captureFrame(){
  if(!activeStream||!preview.videoWidth||!preview.videoHeight){setStatus("Camera frame is not ready yet.");return}
  const maxWidth=1280,scale=Math.min(1,maxWidth/preview.videoWidth);
  const width=Math.max(1,Math.round(preview.videoWidth*scale)),height=Math.max(1,Math.round(preview.videoHeight*scale));
  frameCanvas.width=width;frameCanvas.height=height;
  const context=frameCanvas.getContext("2d",{willReadFrequently:true});
  context.drawImage(preview,0,0,width,height);
  const detection=detectBrightPoints(context,width,height);
  context.save();
  context.strokeStyle="rgba(118,255,184,.95)";
  context.lineWidth=1;
  for(const point of detection.points.slice(0,100)){
    context.beginPath();context.arc(point.x,point.y,5,0,Math.PI*2);context.stroke();
  }
  context.restore();
  frameCanvas.hidden=false;
  frameStatus.textContent=`${width}×${height} frame · ${detection.points.length} bright point candidate${detection.points.length===1?"":"s"} detected. Plate matching is the next stage.`;
}

detectButton.addEventListener("click",populateDevices);
startButton.addEventListener("click",startCamera);
stopButton.addEventListener("click",()=>{stopCamera();setStatus("Camera stopped.")});
captureButton.addEventListener("click",captureFrame);
deviceSelect.addEventListener("change",()=>{saveSettings();if(activeStream){stopCamera();setStatus("Camera selection changed. Start camera to apply.")}});
profileInput.addEventListener("change",saveSettings);
focalLengthInput.addEventListener("change",()=>{saveSettings();if(activeStream)setStatus(cameraDescription())});
sensorWidthInput.addEventListener("change",()=>{saveSettings();if(activeStream)setStatus(cameraDescription())});
window.addEventListener("beforeunload",stopCamera);
if(settingsPanel)new MutationObserver(()=>{if(settingsPanel.hidden&&activeStream)stopCamera()}).observe(settingsPanel,{attributes:true,attributeFilter:["hidden"]});
})();
