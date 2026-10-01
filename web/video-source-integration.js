(()=>{
const settingsDetails=document.querySelector("#camera-settings-details");
const deviceSelect=document.querySelector("#camera-device");
const detectButton=document.querySelector("#camera-detect");
const startButton=document.querySelector("#camera-start");
const stopButton=document.querySelector("#camera-stop");
const captureButton=document.querySelector("#camera-capture-frame");
const status=document.querySelector("#camera-status");
const previewShell=document.querySelector("#camera-preview-shell");
const preview=document.querySelector("#camera-preview");
const frameCanvas=document.querySelector("#camera-frame");
const frameStatus=document.querySelector("#camera-frame-status");
if(!settingsDetails||!deviceSelect||!detectButton||!startButton||!stopButton||!captureButton||!status||!previewShell||!preview||!frameCanvas||!frameStatus)return;

const MODE_KEY="nightazimuth.videoSourceMode";
const NETWORK_URL_KEY="nightazimuth.networkVideoPlaybackUrl";
const NETWORK_PROTOCOL_KEY="nightazimuth.networkVideoUpstreamProtocol";
const DEVICE_KEY="nightazimuth.cameraDeviceId";
const YOLO_PATTERN=/\b(yolobox|yololiv|yolo\s*box)\b/i;
let networkActive=false;

const sourceSection=document.createElement("div");
sourceSection.className="radar-settings video-source-settings";
sourceSection.innerHTML=`
  <h3>Video source</h3>
  <div class="radar-settings-grid">
    <label for="video-source-mode">Source type
      <select id="video-source-mode">
        <option value="direct">Direct camera / webcam</option>
        <option value="yolobox">YoloBox UVC</option>
        <option value="network">Network stream bridge</option>
      </select>
    </label>
    <label id="network-protocol-label" for="network-source-protocol" hidden>YoloBox / upstream protocol
      <select id="network-source-protocol">
        <option value="rtsp">RTSP</option>
        <option value="srt">SRT</option>
        <option value="rtmp">RTMP</option>
        <option value="ndi">NDI</option>
        <option value="other">Other</option>
      </select>
    </label>
    <label id="network-url-label" for="network-playback-url" hidden>Browser playback URL
      <input id="network-playback-url" type="url" inputmode="url" placeholder="https://bridge.example/live/stream.m3u8" autocomplete="off">
    </label>
  </div>
  <p id="video-source-help" class="muted"></p>
`;
const firstGrid=settingsDetails.querySelector(".radar-settings-grid");
(firstGrid?.parentElement||settingsDetails).insertAdjacentElement("beforebegin",sourceSection);

const modeSelect=sourceSection.querySelector("#video-source-mode");
const protocolLabel=sourceSection.querySelector("#network-protocol-label");
const protocolSelect=sourceSection.querySelector("#network-source-protocol");
const networkUrlLabel=sourceSection.querySelector("#network-url-label");
const networkUrlInput=sourceSection.querySelector("#network-playback-url");
const help=sourceSection.querySelector("#video-source-help");
if(!modeSelect||!protocolLabel||!protocolSelect||!networkUrlLabel||!networkUrlInput||!help)return;

function selectedMode(){return modeSelect.value||"direct"}
function isYoloLabel(text){return YOLO_PATTERN.test(String(text||""))}
function videoOptions(){return [...deviceSelect.options].filter(option=>option.value)}
function yoloOptions(){return videoOptions().filter(option=>isYoloLabel(option.textContent))}
function savedNetworkUrl(){return localStorage.getItem(NETWORK_URL_KEY)||""}

function stopNetwork(){
  if(!networkActive)return;
  networkActive=false;
  try{preview.pause()}catch{}
  preview.removeAttribute("src");
  preview.load();
  previewShell.hidden=true;
  startButton.disabled=false;
  stopButton.disabled=true;
  captureButton.disabled=true;
}

function setModeUi(){
  const mode=selectedMode();
  localStorage.setItem(MODE_KEY,mode);
  const network=mode==="network";
  protocolLabel.hidden=!network;
  networkUrlLabel.hidden=!network;
  deviceSelect.disabled=network;
  detectButton.disabled=network;
  if(mode==="yolobox"){
    detectButton.textContent="Detect video sources";
    help.textContent="Connect the DSLR/mirrorless camera to the YoloBox by HDMI, then connect the YoloBox UVC output to this computer. NightAzimuth will prefer a detected YoloBox/YoloLiv video device and keeps live preview, frame capture and plate solving local.";
  }else if(network){
    detectButton.textContent="Detect video sources";
    help.textContent="RTSP, SRT, RTMP and NDI are not browser playback protocols. Supply a browser-compatible HTTPS playback URL from a local or trusted gateway (for example native HLS where supported). The upstream protocol is stored only as connection metadata.";
  }else{
    detectButton.textContent="Detect video sources";
    help.textContent="Use a camera, webcam or HDMI capture device exposed to the browser as a local video input.";
  }
  if(!network&&networkActive)stopNetwork();
  if(mode==="yolobox")preferYoloBox();
}

function preferYoloBox(){
  if(selectedMode()!=="yolobox")return false;
  const matches=yoloOptions();
  if(!matches.length){
    status.textContent="No YoloBox UVC source detected yet. Connect the YoloBox USB/UVC output, then choose Detect video sources.";
    return false;
  }
  const saved=localStorage.getItem(DEVICE_KEY)||"";
  const preferred=matches.find(option=>option.value===saved)||matches[0];
  deviceSelect.value=preferred.value;
  localStorage.setItem(DEVICE_KEY,preferred.value);
  status.textContent=`YoloBox UVC ready · ${preferred.textContent||"video source"}.`;
  return true;
}

const observer=new MutationObserver(()=>{
  if(selectedMode()==="yolobox")queueMicrotask(preferYoloBox);
});
observer.observe(deviceSelect,{childList:true,subtree:true});

detectButton.addEventListener("click",()=>{
  if(selectedMode()!=="yolobox")return;
  setTimeout(preferYoloBox,250);
  setTimeout(preferYoloBox,1000);
});

function validNetworkUrl(){
  const raw=networkUrlInput.value.trim();
  if(!raw)return null;
  try{
    const url=new URL(raw);
    if(url.protocol!=="https:"&&url.protocol!=="http:")return null;
    return url.href;
  }catch{return null}
}

async function startNetwork(event){
  if(selectedMode()!=="network")return;
  event.preventDefault();
  event.stopImmediatePropagation();
  const url=validNetworkUrl();
  if(!url){
    status.textContent="Enter a valid HTTP/HTTPS browser playback URL from the stream bridge.";
    return;
  }
  localStorage.setItem(NETWORK_URL_KEY,url);
  localStorage.setItem(NETWORK_PROTOCOL_KEY,protocolSelect.value);
  startButton.disabled=true;
  status.textContent=`Opening ${protocolSelect.value.toUpperCase()} bridge playback…`;
  try{
    preview.srcObject=null;
    preview.crossOrigin="anonymous";
    preview.src=url;
    preview.playsInline=true;
    await preview.play();
    networkActive=true;
    previewShell.hidden=false;
    stopButton.disabled=false;
    captureButton.disabled=false;
    const resolution=preview.videoWidth&&preview.videoHeight?`${preview.videoWidth}×${preview.videoHeight}`:"live";
    status.textContent=`Network video · ${protocolSelect.value.toUpperCase()} bridge · ${resolution}`;
  }catch{
    networkActive=false;
    preview.removeAttribute("src");
    preview.load();
    startButton.disabled=false;
    stopButton.disabled=true;
    captureButton.disabled=true;
    status.textContent="Unable to play that network URL in this browser. Use a browser-compatible HTTPS/HLS endpoint from the RTSP/SRT/RTMP/NDI gateway.";
  }
}

function stopNetworkEvent(event){
  if(selectedMode()!=="network"&&!networkActive)return;
  event.preventDefault();
  event.stopImmediatePropagation();
  stopNetwork();
  status.textContent="Network video stopped.";
}

function captureNetworkFrame(event){
  if(!networkActive)return;
  event.preventDefault();
  event.stopImmediatePropagation();
  if(!preview.videoWidth||!preview.videoHeight){status.textContent="Network frame is not ready yet.";return}
  const maxWidth=1280;
  const scale=Math.min(1,maxWidth/preview.videoWidth);
  const width=Math.max(1,Math.round(preview.videoWidth*scale));
  const height=Math.max(1,Math.round(preview.videoHeight*scale));
  frameCanvas.width=width;
  frameCanvas.height=height;
  try{
    const context=frameCanvas.getContext("2d",{willReadFrequently:true});
    context.drawImage(preview,0,0,width,height);
    context.getImageData(0,0,1,1);
    frameCanvas.hidden=false;
    frameStatus.textContent=`${width}×${height} network frame captured. For automatic plate solving, use YoloBox UVC; network capture is preview/reference only in this browser path.`;
  }catch{
    frameCanvas.hidden=true;
    frameStatus.textContent="The stream is playing, but the gateway does not allow browser frame capture (CORS). Enable cross-origin access on the playback gateway or use YoloBox UVC.";
  }
}

startButton.addEventListener("click",startNetwork,true);
stopButton.addEventListener("click",stopNetworkEvent,true);
captureButton.addEventListener("click",captureNetworkFrame,true);

modeSelect.value=localStorage.getItem(MODE_KEY)||"direct";
protocolSelect.value=localStorage.getItem(NETWORK_PROTOCOL_KEY)||"rtsp";
networkUrlInput.value=savedNetworkUrl();
modeSelect.addEventListener("change",setModeUi);
protocolSelect.addEventListener("change",()=>localStorage.setItem(NETWORK_PROTOCOL_KEY,protocolSelect.value));
networkUrlInput.addEventListener("change",()=>{
  const url=validNetworkUrl();
  if(url)localStorage.setItem(NETWORK_URL_KEY,url);
  else if(!networkUrlInput.value.trim())localStorage.removeItem(NETWORK_URL_KEY);
});

window.NightAzimuthVideoSources={
  get mode(){return selectedMode()},
  get yoloBoxDetected(){return yoloOptions().length>0},
  get yoloBoxDevices(){return yoloOptions().map(option=>({id:option.value,label:option.textContent||"YoloBox"}))},
  get networkProtocol(){return protocolSelect.value},
  get networkPlaybackUrl(){return networkUrlInput.value.trim()}
};

setModeUi();
})();