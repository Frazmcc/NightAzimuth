(()=>{
const settingsDetails=document.querySelector("#camera-settings-details");
const deviceSelect=document.querySelector("#camera-device");
const detectButton=document.querySelector("#camera-detect");
const startButton=document.querySelector("#camera-start");
const stopButton=document.querySelector("#camera-stop");
const captureButton=document.querySelector("#camera-capture-frame");
const status=document.querySelector("#camera-status");
const preview=document.querySelector("#camera-preview");
if(!settingsDetails||!deviceSelect||!detectButton||!startButton||!stopButton||!captureButton||!status||!preview)return;

const MODE_KEY="nightazimuth.videoSourceMode";
const NETWORK_URL_KEY="nightazimuth.networkVideoPlaybackUrl";
const NETWORK_PROTOCOL_KEY="nightazimuth.networkVideoUpstreamProtocol";
const DEVICE_KEY="nightazimuth.cameraDeviceId";
const YOLO_PATTERN=/\b(yolobox|yololiv|yolo\s*box)\b/i;

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
    <label id="network-url-label" for="network-playback-url" hidden>Browser bridge URL
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
// Explicit IDs keep the hosted DOM contract checker aware of dynamically-created controls.
modeSelect.id="video-source-mode";
protocolLabel.id="network-protocol-label";
protocolSelect.id="network-source-protocol";
networkUrlLabel.id="network-url-label";
networkUrlInput.id="network-playback-url";
help.id="video-source-help";

function selectedMode(){return modeSelect.value||"direct"}
function isYoloLabel(text){return YOLO_PATTERN.test(String(text||""))}
function videoOptions(){return [...deviceSelect.options].filter(option=>option.value)}
function yoloOptions(){return videoOptions().filter(option=>isYoloLabel(option.textContent))}
function savedNetworkUrl(){return localStorage.getItem(NETWORK_URL_KEY)||""}

function validNetworkUrl(){
  const raw=networkUrlInput.value.trim();
  if(!raw)return null;
  try{
    const url=new URL(raw);
    return url.protocol==="https:"?url.href:null;
  }catch{return null}
}

function networkSummary(){
  const url=validNetworkUrl();
  if(!url)return `${protocolSelect.value.toUpperCase()} upstream selected · add an HTTPS browser bridge URL.`;
  return `${protocolSelect.value.toUpperCase()} upstream configured · browser bridge saved.`;
}

function setModeUi(){
  const mode=selectedMode();
  localStorage.setItem(MODE_KEY,mode);
  const network=mode==="network";
  protocolLabel.hidden=!network;
  networkUrlLabel.hidden=!network;
  deviceSelect.disabled=network;
  detectButton.disabled=network;
  detectButton.textContent="Detect video sources";

  if(network){
    if(preview.srcObject&&!stopButton.disabled)stopButton.click();
    startButton.disabled=true;
    stopButton.disabled=true;
    captureButton.disabled=true;
    help.textContent="RTSP, SRT, RTMP and NDI are upstream transport options, not browser playback formats. Save the protocol and an HTTPS browser-bridge URL here for a future/local gateway integration. For live preview, capture and plate solving today, use YoloBox UVC.";
    status.textContent=networkSummary();
    return;
  }

  startButton.disabled=false;
  if(mode==="yolobox"){
    help.textContent="Connect the DSLR/mirrorless camera to the YoloBox by HDMI, then connect the YoloBox UVC output to this computer. NightAzimuth prefers a detected YoloBox/YoloLiv video device and keeps preview, frame capture and plate solving local.";
    preferYoloBox();
  }else{
    help.textContent="Use a camera, webcam or HDMI capture device exposed to the browser as a local video input.";
  }
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

modeSelect.value=localStorage.getItem(MODE_KEY)||"direct";
protocolSelect.value=localStorage.getItem(NETWORK_PROTOCOL_KEY)||"rtsp";
networkUrlInput.value=savedNetworkUrl();
modeSelect.addEventListener("change",setModeUi);
protocolSelect.addEventListener("change",()=>{
  localStorage.setItem(NETWORK_PROTOCOL_KEY,protocolSelect.value);
  if(selectedMode()==="network")status.textContent=networkSummary();
});
networkUrlInput.addEventListener("change",()=>{
  const url=validNetworkUrl();
  if(url)localStorage.setItem(NETWORK_URL_KEY,url);
  else if(!networkUrlInput.value.trim())localStorage.removeItem(NETWORK_URL_KEY);
  if(selectedMode()==="network")status.textContent=networkSummary();
});

window.NightAzimuthVideoSources={
  get mode(){return selectedMode()},
  get yoloBoxDetected(){return yoloOptions().length>0},
  get yoloBoxDevices(){return yoloOptions().map(option=>({id:option.value,label:option.textContent||"YoloBox"}))},
  get networkProtocol(){return protocolSelect.value},
  get networkBridgeUrl(){return validNetworkUrl()}
};

setModeUi();
})();