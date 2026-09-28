// Live Sky layout and runtime performance helpers.
// Keep expensive DOM/layout work out of the per-object projection hot path and
// coalesce repeated redraw requests into one browser animation frame.
(function(){
  const dock=document.querySelector('.layer-dock');
  let cachedBottomReserve=68;
  let drawFrame=null;

  function updateBottomReserve(){
    const next=Math.max(68,(dock?.offsetHeight||44)+32);
    const changed=Math.abs(next-cachedBottomReserve)>.5;
    cachedBottomReserve=next;
    return changed;
  }

  updateBottomReserve();

  verticalFovFor=function(w=canvas.clientWidth||innerWidth,h=canvas.clientHeight||innerHeight){
    const usableHeight=Math.max(160,h-cachedBottomReserve);
    return Math.min(90,fov*usableHeight/Math.max(w,1));
  };

  skyXY=function(az,el,w,h){
    const usableHeight=Math.max(160,h-cachedBottomReserve);
    const off=angularDifference(az,facing);
    const verticalFov=verticalFovFor(w,h);
    const elOff=el-elevationCentre;
    if(Math.abs(off)>fov/2||Math.abs(elOff)>verticalFov/2||el<0||el>90)return null;
    return [
      w*.06+(.5+off/fov)*w*.88,
      usableHeight*.5-(elOff/verticalFov)*usableHeight*.9
    ];
  };

  // drawSky is called by pointer movement, several API completions, satellite
  // animation and resize handlers. Render at most once per animation frame so a
  // burst of updates cannot redraw the whole sky several times before paint.
  const renderSkyNow=drawSky;
  drawSky=function(){
    if(drawFrame!==null)return;
    drawFrame=requestAnimationFrame(()=>{
      drawFrame=null;
      renderSkyNow();
    });
  };

  if(dock&&typeof ResizeObserver!=="undefined"){
    new ResizeObserver(()=>{if(updateBottomReserve())drawSky()}).observe(dock);
  }else{
    window.addEventListener("resize",()=>{if(updateBottomReserve())drawSky()});
  }

  // De-duplicate identical API work and keep slow-changing data warm in the
  // browser. Cache keys include observer coordinates and all query parameters,
  // so changing location cannot reuse data from the previous observer.
  if(typeof getJson==="function"){
    const baseGetJson=getJson;
    const responseCache=new Map();
    const inFlight=new Map();
    const ttlForPath=path=>path==="/api/v1/airports"?60*60*1000:
      path==="/api/v1/weather"||path==="/api/v1/observing"?5*60*1000:
      path==="/api/v1/sky"?30*1000:
      path==="/api/v1/aircraft"?14*1000:0;
    const requestKey=(path,params)=>{
      const entries=Object.entries(params||{}).sort(([a],[b])=>a.localeCompare(b));
      return `${path}?${entries.map(([key,value])=>`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`).join("&")}`;
    };

    getJson=async function(path,params={},options={}){
      const key=requestKey(path,params);
      const now=Date.now();
      const ttl=ttlForPath(path);
      const cached=responseCache.get(key);
      if(ttl>0&&cached&&now-cached.storedAt<ttl)return cached.data;
      if(inFlight.has(key))return inFlight.get(key);
      const request=Promise.resolve(baseGetJson(path,params,options)).then(data=>{
        if(ttl>0)responseCache.set(key,{storedAt:Date.now(),data});
        return data;
      }).finally(()=>inFlight.delete(key));
      inFlight.set(key,request);
      return request;
    };
  }

  // Saving a new observer while a refresh is already running used to allow old
  // location responses to paint the new view because refresh() simply returned
  // while busy. Invalidate that generation immediately and run the new observer
  // refresh as soon as the old request group has finished.
  const locationForm=document.querySelector("#settings-location-form");
  if(locationForm&&typeof refresh==="function"){
    locationForm.addEventListener("submit",()=>{
      let waitForCurrent=false;
      try{
        refreshGeneration++;
        waitForCurrent=Boolean(refreshInFlight);
      }catch{}
      if(!waitForCurrent)return;
      const rerun=()=>{
        try{
          if(refreshInFlight){setTimeout(rerun,50);return}
          refresh().catch(()=>{refreshInFlight=false;statusEl.textContent="API UNAVAILABLE"});
        }catch{}
      };
      setTimeout(rerun,0);
    },{capture:true});
  }

  requestAnimationFrame(()=>drawSky());
})();
