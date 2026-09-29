// Run the CPU-heavy star-pattern search away from the browser UI thread.
importScripts("./camera-plate-solver.js?v=21.11.18");

self.onmessage=event=>{
  try{
    const solver=self.NightAzimuthPlateSolver;
    if(!solver)throw new Error("Plate solver did not initialise in worker.");
    const solution=solver.solve(event.data||{});
    self.postMessage({solution});
  }catch(error){
    self.postMessage({error:String(error?.message||error||"Plate solver worker failed.")});
  }
};
