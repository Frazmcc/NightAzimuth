const forecastColourRoot=document.querySelector("#forecast-hours");

function cloudCoverBucket(value){
  const percent=Math.max(0,Math.min(100,Number(value)));
  return Math.round(percent/5)*5;
}

function cloudViewingLabel(percent){
  if(percent<=10)return "Excellent viewing potential";
  if(percent<=30)return "Good viewing potential";
  if(percent<=55)return "Mixed viewing potential";
  if(percent<=80)return "Poor viewing potential";
  return "Very poor viewing potential";
}

function ensureForecastColourKey(){
  if(document.querySelector("#forecast-colour-key"))return;
  const status=document.querySelector("#forecast-status");
  if(!status)return;
  const key=document.createElement("div");
  key.id="forecast-colour-key";
  key.className="forecast-colour-key";
  key.setAttribute("aria-label","Cloud cover viewing guide: green is clearer and better for viewing; amber is mixed; red is cloudier and worse for viewing.");
  const caption=document.createElement("div");
  caption.className="forecast-colour-key-caption";
  caption.textContent="Cloud cover viewing guide · greener = clearer sky";
  const labels=document.createElement("div");
  labels.className="forecast-colour-key-labels";
  for(const text of ["0% · BEST","50% · MIXED","100% · WORST"]){
    const span=document.createElement("span");
    span.textContent=text;
    labels.append(span);
  }
  const bar=document.createElement("div");
  bar.className="forecast-colour-key-bar";
  bar.setAttribute("aria-hidden","true");
  key.append(caption,labels,bar);
  status.insertAdjacentElement("afterend",key);
}

function applyForecastCloudColours(){
  if(!forecastColourRoot)return;
  ensureForecastColourKey();
  for(const value of forecastColourRoot.querySelectorAll(".forecast-table td strong")){
    const percent=Number.parseFloat(value.textContent);
    if(!Number.isFinite(percent))continue;
    const bounded=Math.max(0,Math.min(100,percent));
    const cell=value.closest("td");
    if(!cell)continue;
    for(const className of [...cell.classList]){
      if(className.startsWith("cloud-cover-")&&className!=="cloud-cover-cell")cell.classList.remove(className);
    }
    cell.classList.add("forecast-cloud-cell",`cloud-cover-${cloudCoverBucket(bounded)}`);
    value.classList.add("forecast-cloud-value");
    const description=`${Math.round(bounded)}% cloud cover · ${cloudViewingLabel(bounded)}`;
    value.title=description;
    value.setAttribute("aria-label",description);
  }
}

if(forecastColourRoot){
  new MutationObserver(applyForecastCloudColours).observe(forecastColourRoot,{childList:true,subtree:true});
  applyForecastCloudColours();
}
