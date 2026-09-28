// Live satellite motion and identification helpers.
// The API supplies 60 seconds of predicted observer-relative positions so the
// browser can animate known satellites smoothly without polling the server every second.
(function(){
  const UPDATE_MS=250;
  const TRAIN_COUNT_UPDATE_MS=5000;
  const preparedTracks=new WeakMap();
  let lastDraw=0;
  let lastTrainCountUpdate=0;
  let lastCatalogue=null;

  function shortestAzimuthDelta(from,to){return((to-from+540)%360)-180}

  function preparedTrack(satellite){
    const source=Array.isArray(satellite.track)?satellite.track:[];
    const cached=preparedTracks.get(satellite);
    if(cached&&cached.source===source)return cached.points;
    const points=source.map(point=>({
      time:Number.isFinite(point._nightazimuth_time)?point._nightazimuth_time:Date.parse(point.time_utc),
      azimuth:Number(point.azimuth_deg),
      elevation:Number(point.elevation_deg),
      range:Number(point.range_km)
    })).filter(point=>Number.isFinite(point.time)&&Number.isFinite(point.azimuth)&&Number.isFinite(point.elevation)&&Number.isFinite(point.range));
    preparedTracks.set(satellite,{source,points});
    return points;
  }

  function interpolateTrack(satellite,nowMs){
    const points=preparedTrack(satellite);
    if(points.length<2)return false;
    let leftIndex=0,rightIndex=1;
    const finalIndex=points.length-1;
    if(nowMs>=points[finalIndex].time){leftIndex=finalIndex-1;rightIndex=finalIndex}
    else if(nowMs>points[0].time){
      for(let i=0;i<finalIndex;i++){
        if(nowMs>=points[i].time&&nowMs<=points[i+1].time){leftIndex=i;rightIndex=i+1;break}
      }
    }
    const left=points[leftIndex],right=points[rightIndex];
    const span=Math.max(1,right.time-left.time);
    const ratio=Math.max(0,Math.min(1,(nowMs-left.time)/span));
    satellite.azimuth_deg=(left.azimuth+shortestAzimuthDelta(left.azimuth,right.azimuth)*ratio+360)%360;
    satellite.elevation_deg=left.elevation+(right.elevation-left.elevation)*ratio;
    satellite.range_km=left.range+(right.range-left.range)*ratio;
    return true;
  }

  function updateTrainCounts(){
    const counts=new Map();
    for(const satellite of skySatellites){
      satellite.identification_status="Known tracked satellite";
      satellite.visible_train_count=null;
      if(satellite.category!=="Starlink"||!satellite.launch_id||Number(satellite.elevation_deg)<0)continue;
      counts.set(satellite.launch_id,(counts.get(satellite.launch_id)||0)+1);
    }
    for(const satellite of skySatellites){
      if(satellite.category==="Starlink"&&satellite.launch_id){
        const count=counts.get(satellite.launch_id)||0;
        satellite.visible_train_count=count>=2?count:null;
      }
    }
  }

  function trackedSatellite(satellite){
    if(typeof trackedObject==="undefined"||trackedObject?.kind!=="satellite")return false;
    const key=satellite.norad_id||satellite.name;
    return trackedObject.key===key;
  }

  function drawPredictedSatellitePaths(w,h){
    if(!layers.satellites)return;
    ctx.save();
    ctx.lineWidth=1;
    for(const satellite of skySatellites){
      // Do not walk seven future points for every ACTIVE catalogue object when
      // its current position is nowhere near the viewport. The object itself is
      // still retained and drawn as soon as it enters view.
      if(!trackedSatellite(satellite)&&!skyXY(Number(satellite.azimuth_deg),Number(satellite.elevation_deg),w,h))continue;
      const track=Array.isArray(satellite.track)?satellite.track:[];
      if(track.length<2)continue;
      ctx.strokeStyle=satellite.category==="Starlink"?"rgba(112,220,255,.34)":"rgba(255,215,106,.20)";
      ctx.beginPath();
      let drawing=false;
      for(const point of track){
        const xy=skyXY(Number(point.azimuth_deg),Number(point.elevation_deg),w,h);
        if(!xy){drawing=false;continue}
        if(!drawing){ctx.moveTo(xy[0],xy[1]);drawing=true}else ctx.lineTo(xy[0],xy[1]);
      }
      ctx.stroke();
    }
    ctx.restore();
  }

  const originalDrawContacts=drawContacts;
  drawContacts=function(w,h){drawPredictedSatellitePaths(w,h);originalDrawContacts(w,h)};

  const originalShowObject=showObject;
  showObject=function(target){
    originalShowObject(target);
    if(target.kind!=="satellite")return;
    const satellite=target.item;
    const detailRows=[
      ["Identification","Known tracked satellite"],
      ["Category",satellite.category],
      ["International designator",satellite.object_id],
      ["Launch / train",satellite.launch_id],
      ["Visible in same Starlink launch",satellite.visible_train_count],
      ["Catalogues",Array.isArray(satellite.source_groups)?satellite.source_groups.join(", "):satellite.source_groups],
      ["Element epoch",satellite.epoch_utc],
      ["Inclination",satellite.inclination_deg==null?null:`${Number(satellite.inclination_deg).toFixed(2)}°`],
      ["Orbital period",satellite.period_minutes==null?null:`${Number(satellite.period_minutes).toFixed(2)} min`],
      ["Eccentricity",satellite.eccentricity],
      ["Slant range",satellite.range_km==null?null:`${Number(satellite.range_km).toFixed(1)} km`]
    ].filter(([,value])=>value!=null&&value!=="");
    const details=document.querySelector("#inspector-details");
    for(const [label,value] of detailRows){
      const row=document.createElement("div"),key=document.createElement("span"),data=document.createElement("strong");
      key.textContent=label;data.textContent=String(value);row.append(key,data);details.append(row);
    }
  };

  function animate(now){
    if(!document.hidden&&now-lastDraw>=UPDATE_MS){
      const current=Date.now();
      const satelliteLayerVisible=typeof layers!=="undefined"&&layers.satellites!==false;
      const followingSatellite=typeof trackedObject!=="undefined"&&trackedObject?.kind==="satellite";
      if(satelliteLayerVisible||followingSatellite){
        let moved=false;
        for(const satellite of skySatellites)moved=interpolateTrack(satellite,current)||moved;
        if(lastCatalogue!==skySatellites||current-lastTrainCountUpdate>=TRAIN_COUNT_UPDATE_MS){
          updateTrainCounts();
          lastCatalogue=skySatellites;
          lastTrainCountUpdate=current;
        }
        if(moved)drawSky();
      }
      lastDraw=now;
    }
    requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);
})();
