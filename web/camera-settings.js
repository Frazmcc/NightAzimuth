(()=>{
const deviceSelect=document.querySelector("#camera-device");
const detectButton=document.querySelector("#camera-detect");
const profileInput=document.querySelector("#camera-profile");
const focalLengthInput=document.querySelector("#camera-focal-length");
const status=document.querySelector("#camera-status");
if(!deviceSelect||!detectButton||!profileInput||!focalLengthInput||!status)return;

const DEVICE_KEY="nightazimuth.cameraDeviceId";
const PROFILE_KEY="nightazimuth.cameraProfile";
const FOCAL_KEY="nightazimuth.cameraFocalLengthMm";

profileInput.value=localStorage.getItem(PROFILE_KEY)||"Sony A7S Gen 1";
focalLengthInput.value=localStorage.getItem(FOCAL_KEY)||"";

function setStatus(message){status.textContent=message}
function saveSettings(){
  if(deviceSelect.value)localStorage.setItem(DEVICE_KEY,deviceSelect.value);
  else localStorage.removeItem(DEVICE_KEY);
  localStorage.setItem(PROFILE_KEY,profileInput.value.trim()||"Sony A7S Gen 1");
  if(focalLengthInput.value)localStorage.setItem(FOCAL_KEY,focalLengthInput.value);
  else localStorage.removeItem(FOCAL_KEY);
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

detectButton.addEventListener("click",populateDevices);
deviceSelect.addEventListener("change",saveSettings);
profileInput.addEventListener("change",saveSettings);
focalLengthInput.addEventListener("change",saveSettings);
})();
