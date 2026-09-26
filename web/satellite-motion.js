// Live satellite motion and identification helpers.
// The API supplies 60 seconds of predicted observer-relative positions so the
// browser can animate known satellites smoothly without polling the server every second.
(function(){
  const UPDATE_MS=250;
  let lastDraw=0;

  function shortestAzimuthDelta(from,to){return((to-from+540)%360)-180}

  function interpolateTrack(satellite,nowMs){
    const track=Array.isArray(satellite.track)?satellite.track:[];
    if(track.length<2)return false;
    const points=track.map(point=>({...point,_time:Date.parse(point.time_utc)})).filter(point=>Number.isFinite(point._time));
    if(points.length<2)return false;
    let left=points[0],right=points[points.length-1];
    if(nowMs<=left._time){right=points[1]}
    else if(nowMs>=right._time){left=points[points.length-2]}
    else{
      for(let i=0;i<points.length-1;i++){
        if(nowMs>=points[i]._time&&nowMs<=points[i+1]._time){left=points[i];right=points[i+1];break}
      }
    }
    const span=Math.max(1,right._time-left._time);
    const ratio=Math.max(0,Math.min(1,(nowMs-left._time)/span));
    const leftAz=Number(left.azimuth_deg),rightAz=Number(right.azimuth_deg);
    satellite.azimuth_deg=(leftAz+shortestAzimuthDelta(leftAz,rightAz)*ratio+360)%360;
    satellite.elevation_deg=Number(left.elevation_deg)+(Number(right.elevation_deg)-Number(left.elevation_deg))*ratio;
    satellite.range_km=Number(left.range_km)+(Number(right.range_km)-Number(left.range_km))*ratio;
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

  function drawPredictedSatellitePaths(w,h){
    if(!layers.satellites)return;
    ctx.save();
    ctx.lineWidth=1;
    for(const satellite of skySatellites){
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
    if(now-lastDraw>=UPDATE_MS){
      const current=Date.now();
      let moved=false;
      for(const satellite of skySatellites)moved=interpolateTrack(satellite,current)||moved;
      if(moved){updateTrainCounts();drawSky()}
      lastDraw=now;
    }
    requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);
})();
