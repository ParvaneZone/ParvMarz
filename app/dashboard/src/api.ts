/** Thin fetch wrapper for the admin API: cookie session, CSRF-style header, readable error messages. */
export const api = async (path:string, init:RequestInit={}) => {
 const response=await fetch(path,{...init,credentials:"same-origin",headers:{"Content-Type":"application/json","X-Requested-With":"jx",...(init.headers||{})}});
 const data=await response.json().catch(()=>({}));
 if(!response.ok){
  const d=data?.detail; let text="";
  if(typeof d==="string") text=d;
  else if(Array.isArray(d)) text=d.map((x:any)=>`${(x.loc||[]).filter((p:string)=>!["body","query"].includes(p)).join(".")||"body"}: ${x.msg}`).join("؛ ");
  else if(d&&typeof d==="object") text=d.detail||JSON.stringify(d);
  const code=d&&typeof d==="object"&&d.code?` [${d.code}]`:"";
  throw new Error((text||`HTTP ${response.status}`)+code+` (${init.method||"GET"} ${path} → ${response.status})`);
 }
 return data;
};
export const subUrl=(u:{subscription_url:string|null})=>/^https?:\/\//.test(u.subscription_url||"")?String(u.subscription_url):location.origin+u.subscription_url;
export const errMsg=(e:unknown)=>e instanceof Error?e.message:String(e);
