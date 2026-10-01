(()=>{
const layerDefaults={
  stars:true,
  constellations:false,
  galaxies:true,
  planets:true,
  airports:true,
  aircraft:true,
  satellites:true
};
const labelDefaults={
  stars:true,
  galaxies:false,
  planets:true,
  airports:true,
  aircraft:true,
  satellites:false
};

for(const input of document.querySelectorAll("[data-layer]")){
  const key=input.dataset.layer;
  if(Object.hasOwn(layerDefaults,key))input.checked=layerDefaults[key];
}
for(const input of document.querySelectorAll("[data-label-layer]")){
  const key=input.dataset.labelLayer;
  if(Object.hasOwn(labelDefaults,key))input.checked=labelDefaults[key];
}

if(typeof layers!=="undefined")Object.assign(layers,layerDefaults);
if(typeof labels!=="undefined")Object.assign(labels,labelDefaults);
if(typeof drawSky==="function")drawSky();

// Load optional video-source enhancements separately so the base camera module
// remains focused on capture and plate solving. The integration adds YoloBox UVC
// discovery plus browser-safe network-bridge controls without duplicating the
// existing camera implementation.
const videoSources=document.createElement("script");
videoSources.src="./video-source-integration.js?v=21.11.26";
videoSources.async=false;
document.head.append(videoSources);

// live-sky-layout.js runs after this module in index.html. Load the depth layer
// only once that projection helper is available so it can replace the legacy
// rectangular projection without racing application startup.
function loadDepthWhenReady(){
  if(typeof verticalFovFor!=="function"||typeof skyXY!=="function"){
    requestAnimationFrame(loadDepthWhenReady);
    return;
  }
  if(document.querySelector('script[data-nightazimuth-depth]'))return;
  const depth=document.createElement("script");
  depth.dataset.nightazimuthDepth="true";
  depth.src="./live-sky-depth.js?v=22.2.0";
  depth.async=false;
  document.head.append(depth);
}
requestAnimationFrame(loadDepthWhenReady);
})();
