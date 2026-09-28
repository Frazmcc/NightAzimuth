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
})();
