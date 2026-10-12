"""NightAzimuth uses ALEN time-labelled SGP4 trajectories without azimuth-wrap jumps."""
from pathlib import Path
import subprocess

APP = Path("web/app.js").read_text(encoding="utf-8")


def test_alen_feed_with_legacy_fallback_and_timed_render():
    assert 'getJson("/api/v1/satellites/alen"' in APP
    assert 'getJson("/api/v1/satellites"' in APP
    assert 'refreshSatelliteTrajectories(observer(),refreshGeneration)' in APP
    assert 'if(!document.hidden&&satelliteTrajectoryMode)drawSky()' in APP
    assert 'satelliteViewPosition(raw)' in APP


def test_trajectory_spherical_interpolation_and_stale_rejection():
    start=APP.index("function satelliteViewPosition(")
    end=APP.index("function drawContacts(",start)
    source=APP[start:end]
    js="""let satelliteTrajectoryMode=true;\n""" + source + """
const sampleTime=Date.parse("2026-10-12T12:00:00Z");
const sat={position_sample_at:"2026-10-12T12:00:00Z",trajectory:[
 {offset_seconds:0,azimuth_deg:359,elevation_deg:30,range_km:500},
 {offset_seconds:2,azimuth_deg:1,elevation_deg:31,range_km:499},
 {offset_seconds:4,azimuth_deg:3,elevation_deg:32,range_km:498}
]};
const half=satelliteViewPosition(sat,sampleTime+1000);
function assert(x){if(!x)throw Error("trajectory contract failed")}
assert(half&&Math.min(Math.abs(half.azimuth_deg),Math.abs(360-half.azimuth_deg))<0.05);
assert(half.elevation_deg>30&&half.elevation_deg<31);
assert(satelliteViewPosition(sat,sampleTime+18000)===null);
satelliteTrajectoryMode=false;
assert(satelliteViewPosition(sat)===sat);
"""
    result=subprocess.run(["node","-e",js],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
