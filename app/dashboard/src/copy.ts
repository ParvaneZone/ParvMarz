export const copyText=async(s:string):Promise<boolean>=>{
  try{await navigator.clipboard.writeText(s);return true}catch{/* insecure context fallback */}
  try{const a=document.createElement("textarea");a.value=s;a.setAttribute("readonly","");a.style.cssText="position:fixed;top:0;left:0;opacity:0";document.body.appendChild(a);a.focus();a.select();a.setSelectionRange(0,s.length);const ok=document.execCommand("copy");a.remove();return ok}catch{return false}
};
