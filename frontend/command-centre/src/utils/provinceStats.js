import { provinceDistribution } from "../data/harvestedRfqs";
export function getTotals(){return provinceDistribution.reduce((a,r)=>({rfqs:a.rfqs+r.rfqs,eligible:a.eligible+r.eligible,value:a.value+r.value,marginWeighted:a.marginWeighted+r.avgMargin*r.eligible}),{rfqs:0,eligible:0,value:0,marginWeighted:0})}
export function intensityForProvince(row){const max=Math.max(...provinceDistribution.map(i=>i.eligible));return row.eligible/max}
export function heatColor(row){const i=intensityForProvince(row);if(i>=.82)return"#ef4444";if(i>=.62)return"#f97316";if(i>=.42)return"#eab308";if(i>=.22)return"#22c55e";return"#38bdf8"}
export function byProvince(name){return provinceDistribution.find(r=>r.province===name||r.code===name)}
