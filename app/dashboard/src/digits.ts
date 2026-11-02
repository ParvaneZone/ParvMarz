/** Persian/Arabic-Indic digits -> ASCII digits (UI numbers are always shown in English). */
export const toEnDigits = (s: string) => s.replace(/[\u06F0-\u06F9\u0660-\u0669]/g, d => String(d.charCodeAt(0) & 15));

/** Date/Number toLocale*() without an explicit locale would follow the browser (fa-IR prints Persian digits): default to en-US. */
function forceEnLocale() {
  const w = globalThis as any; if (w.__jxEnDigits) return; w.__jxEnDigits = true;
  for (const k of ["toLocaleString", "toLocaleDateString", "toLocaleTimeString"]) {
    const orig = (Date.prototype as any)[k];
    (Date.prototype as any)[k] = function (this: Date, l?: any, o?: any) { return orig.call(this, l ?? "en-US", o); };
  }
  const ns = Number.prototype.toLocaleString;
  (Number.prototype as any).toLocaleString = function (this: number, l?: any, o?: any) { return ns.call(this, l ?? "en-US", o); };
}
forceEnLocale();
