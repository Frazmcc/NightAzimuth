// Reserve a dedicated below-horizon band for the layer controls.
// This prevents the layer dock from obscuring objects sitting on the horizon.
(function(){
  function bottomReserve(){
    const dock=document.querySelector('.layer-dock');
    return Math.max(68,(dock?.offsetHeight||44)+32);
  }

  verticalFovFor=function(w=canvas.clientWidth||innerWidth,h=canvas.clientHeight||innerHeight){
    const usableHeight=Math.max(160,h-bottomReserve());
    return Math.min(90,fov*usableHeight/Math.max(w,1));
  };

  skyXY=function(az,el,w,h){
    const usableHeight=Math.max(160,h-bottomReserve());
    const off=angularDifference(az,facing);
    const verticalFov=verticalFovFor(w,h);
    const elOff=el-elevationCentre;
    if(Math.abs(off)>fov/2||Math.abs(elOff)>verticalFov/2||el<0||el>90)return null;
    return [
      w*.06+(.5+off/fov)*w*.88,
      usableHeight*.5-(elOff/verticalFov)*usableHeight*.9
    ];
  };

  requestAnimationFrame(()=>drawSky());
})();
