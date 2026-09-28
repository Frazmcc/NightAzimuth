from __future__ import annotations

import subprocess


def test_browser_plate_solver_recovers_a_synthetic_camera_pointing() -> None:
    script = r'''
const fs=require("fs"),vm=require("vm");
vm.runInThisContext(fs.readFileSync("web/camera-plate-solver.js","utf8"));
const solver=globalThis.NightAzimuthPlateSolver;
const width=1280,height=720,hfov=70;
const expected={az:225,el:35,roll:8};
const rotation=solver._rotationFromPointing(expected.az,expected.el,expected.roll);
const points=[
  {x:180,y:160,luma:255},{x:420,y:130,luma:250},{x:720,y:180,luma:245},
  {x:1030,y:150,luma:240},{x:260,y:390,luma:235},{x:560,y:330,luma:230},
  {x:880,y:410,luma:225},{x:1110,y:500,luma:220},
  {x:90,y:610,luma:100},{x:1190,y:80,luma:90}
];
const stars=points.slice(0,8).map((point,index)=>{
  const ray=solver._cameraRay(point,width,height,hfov);
  const world=rotation.cameraToWorld(ray);
  const altaz=solver._vectorToAltAz(world);
  return {hip_id:1000+index,azimuth_deg:altaz.azimuthDeg,elevation_deg:altaz.elevationDeg,magnitude:index*.2,name:`Test ${index+1}`};
});
const result=solver.solve({points,stars,width,height,estimatedHfovDeg:hfov});
function angleDifference(a,b){return Math.abs(((a-b+540)%360)-180)}
if(!result.locked)throw new Error(`solver did not lock: ${JSON.stringify(result)}`);
if(result.matches<7)throw new Error(`too few matches: ${result.matches}`);
if(angleDifference(result.azimuthDeg,expected.az)>1)throw new Error(`azimuth error: ${result.azimuthDeg}`);
if(Math.abs(result.elevationDeg-expected.el)>1)throw new Error(`elevation error: ${result.elevationDeg}`);
if(Math.abs(result.hfovDeg-hfov)>3)throw new Error(`HFOV error: ${result.hfovDeg}`);
if(result.rmsDeg>.25)throw new Error(`residual too large: ${result.rmsDeg}`);
'''
    completed = subprocess.run(
        ["node", "-e", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
