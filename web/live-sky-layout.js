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

  // Keep the rectangular projection wholly inside the physical 0°–90° sky.
  // This prevents blank bands both below the horizon and above the zenith.
  clampElevationCentre=function(value,w=canvas.clientWidth||innerWidth,h=canvas.clientHeight||innerHeight){
    const halfVertical=verticalFovFor(w,h)/2;
    const numeric=Number(value);
    const requested=Number.isFinite(numeric)?numeric:halfVertical;
    return Math.max(halfVertical,Math.min(90-halfVertical,requested));
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

  elevationCentre=clampElevationCentre(elevationCentre);

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
    new ResizeObserver(()=>{
      if(!updateBottomReserve())return;
      elevationCentre=clampElevationCentre(elevationCentre);
      drawSky();
    }).observe(dock);
  }else{
    window.addEventListener("resize",()=>{
      if(!updateBottomReserve())return;
      elevationCentre=clampElevationCentre(elevationCentre);
      drawSky();
    });
  }

  // De-duplicate identical API work and keep slow-changing data warm in the
  // browser. Cache keys include observer coordinates and all query parameters,
  // so changing location cannot reuse data from the previous observer.
  if(typeof getJson==="function"){
    const baseGetJson=getJson;
    const responseCache=new Map();
    const inFlight=new Map();
    const MAX_RESPONSE_CACHE=48;
    const ttlForPath=path=>path==="/api/v1/airports"?60*60*1000:
      path==="/api/v1/weather"||path==="/api/v1/observing"?5*60*1000:
      path==="/api/v1/sky"?30*1000:
      path==="/api/v1/aircraft"?14*1000:0;
    const effectiveParams=(path,params)=>path==="/api/v1/aircraft"?{
      ...params,
      radius_km:400,
      minimum_elevation_deg:-90,
      include_ground:false
    }:params;
    const requestKey=(path,params)=>{
      const entries=Object.entries(params||{}).sort(([a],[b])=>a.localeCompare(b));
      return `${path}?${entries.map(([key,value])=>`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`).join("&")}`;
    };
    const storeResponse=(key,data)=>{
      responseCache.delete(key);
      responseCache.set(key,{storedAt:Date.now(),data});
      while(responseCache.size>MAX_RESPONSE_CACHE){
        const oldest=responseCache.keys().next().value;
        if(oldest===undefined)break;
        responseCache.delete(oldest);
      }
    };

    // Sky and satellite snapshots are the two heaviest observer-specific calls.
    // Starting both at the same instant multiplied CPU pressure on the small
    // hosted API and contributed to the 4-user production saturation observed in
    // capacity testing. Queue them per browser instead: all lightweight/live
    // requests still start immediately, sky gets first use of the astronomy CPU,
    // and satellites follow. A small stable observer-derived delay prevents many
    // newly opened clients from synchronising on exactly the same millisecond.
    let astronomyTail=Promise.resolve();
    const isHeavyAstronomyPath=path=>path==="/api/v1/sky"||path==="/api/v1/satellites";
    const observerSpreadMs=params=>{
      const lat=Number(params?.latitude||0),lon=Number(params?.longitude||0);
      const a=Math.round((lat+90)*1000),b=Math.round((lon+180)*1000);
      return Math.abs((a*31+b*17)%351);
    };
    const scheduleRequest=(path,params,run)=>{
      if(!isHeavyAstronomyPath(path))return run();
      const baseDelay=path==="/api/v1/satellites"?250:0;
      const delayMs=baseDelay+observerSpreadMs(params);
      const scheduled=astronomyTail.catch(()=>{}).then(()=>new Promise(resolve=>setTimeout(resolve,delayMs))).then(run);
      astronomyTail=scheduled.catch(()=>{});
      return scheduled;
    };

    getJson=async function(path,params={},options={}){
      // aircraft-sensitivity.js normalises every aircraft request to the wider
      // 400 km / -90° acquisition. Use that effective request in the cache key
      // so the 60-second general refresh and 15-second aircraft refresh share
      // the same in-flight response instead of downloading it twice.
      const key=requestKey(path,effectiveParams(path,params));
      const now=Date.now();
      const ttl=ttlForPath(path);
      const cached=responseCache.get(key);
      if(ttl>0&&cached&&now-cached.storedAt<ttl)return cached.data;
      if(inFlight.has(key))return inFlight.get(key);
      const request=scheduleRequest(path,params,()=>Promise.resolve(baseGetJson(path,params,options))).then(data=>{
        if(ttl>0)storeResponse(key,data);
        return data;
      }).finally(()=>inFlight.delete(key));
      inFlight.set(key,request);
      return request;
    };
  }

  // Do not spend bandwidth/CPU refreshing the sky while the page is hidden.
  // Browsers already throttle background animation; this also prevents the
  // minute satellite/API refresh from doing avoidable work in a background tab.
  if(typeof refresh==="function"){
    const baseRefresh=refresh;
    refresh=async function(){
      if(document.hidden)return;
      return baseRefresh();
    };
    document.addEventListener("visibilitychange",()=>{
      if(document.hidden)return;
      refresh().catch(()=>{
        try{refreshInFlight=false;statusEl.textContent="API UNAVAILABLE"}catch{}
      });
    });
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
