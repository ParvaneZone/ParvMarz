import React from "react";

/** Inline SVG icon set (24x24, stroke = currentColor). No emoji anywhere in the UI. */
const P: Record<string, React.ReactNode> = {
  menu: <><path d="M4 6h16" /><path d="M4 12h16" /><path d="M4 18h16" /></>,
  palette: <><path d="M12 3a9 9 0 1 0 0 18c1.1 0 1.8-.8 1.8-1.7 0-.5-.2-.9-.5-1.3-.3-.4-.5-.8-.5-1.3 0-1 .8-1.7 1.8-1.7H17a4 4 0 0 0 4-4c0-4.4-4-8-9-8Z" /><circle cx="7.5" cy="11" r="1" /><circle cx="10.5" cy="7" r="1" /><circle cx="15.5" cy="7.5" r="1" /></>,
  x: <><path d="M6 6l12 12" /><path d="M18 6 6 18" /></>,
  arrowDown: <><path d="M12 4v16" /><path d="m6 14 6 6 6-6" /></>,
  arrowUp: <><path d="M12 20V4" /><path d="m6 10 6-6 6 6" /></>,
  dashboard: <><rect x="3" y="3" width="7" height="9" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" /><rect x="14" y="12" width="7" height="9" rx="1.5" /><rect x="3" y="16" width="7" height="5" rx="1.5" /></>,
  user: <><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4 3.6-7 8-7s8 3 8 7" /></>,
  users: <><circle cx="9" cy="8" r="3.5" /><path d="M2 20c0-3.6 3-6 7-6s7 2.4 7 6" /><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8" /><path d="M18 14.3c2.4.7 4 2.5 4 5.7" /></>,
  server: <><rect x="3" y="3" width="18" height="7" rx="2" /><rect x="3" y="14" width="18" height="7" rx="2" /><path d="M7 6.5h.01" /><path d="M7 17.5h.01" /></>,
  inbound: <><circle cx="12" cy="12" r="2.2" /><path d="M16.2 7.8a6 6 0 0 1 0 8.4" /><path d="M7.8 16.2a6 6 0 0 1 0-8.4" /><path d="M19 5a10 10 0 0 1 0 14" /><path d="M5 19A10 10 0 0 1 5 5" /></>,
  layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m3 13 9 5 9-5" /></>,
  template: <><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z" /><path d="M14 3v5h5" /><path d="M9 13h6" /><path d="M9 17h6" /></>,
  shield: <><path d="M12 3 4 6v6c0 4.5 3.2 8 8 9 4.8-1 8-4.5 8-9V6l-8-3Z" /><path d="m9 12 2 2 4-4" /></>,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" /></>,
  cpu: <><rect x="6" y="6" width="12" height="12" rx="2" /><rect x="9.5" y="9.5" width="5" height="5" rx=".8" /><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3" /></>,
  memory: <><rect x="2" y="7" width="20" height="10" rx="2" /><path d="M6 11v2M10 11v2M14 11v2M18 11v2" /><path d="M5 17v3M19 17v3" /></>,
  swap: <><path d="M7 4 3 8l4 4" /><path d="M3 8h14" /><path d="m17 12 4 4-4 4" /><path d="M21 16H7" /></>,
  disk: <><ellipse cx="12" cy="6" rx="8" ry="3" /><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6" /><path d="M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  activity: <path d="M3 12h4l3-8 4 16 3-8h4" />,
  database: <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5" /><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></>,
  gauge: <><path d="M4 18a9 9 0 1 1 16 0" /><path d="m12 14 4-5" /><circle cx="12" cy="14" r="1.2" /></>,
  plus: <><path d="M12 5v14" /><path d="M5 12h14" /></>,
  refresh: <><path d="M21 12a9 9 0 0 1-15.5 6.2L3 16" /><path d="M3 21v-5h5" /><path d="M3 12A9 9 0 0 1 18.5 5.8L21 8" /><path d="M21 3v5h-5" /></>,
  trash: <><path d="M4 7h16" /><path d="M10 11v6M14 11v6" /><path d="M6 7l1 13h10l1-13" /><path d="M9 7V4h6v3" /></>,
  edit: <><path d="M4 20h4L19 9l-4-4L4 16v4Z" /><path d="m13.5 6.5 4 4" /></>,
  check: <path d="m5 12 5 5 9-10" />,
  logout: <><path d="M10 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h5" /><path d="m16 8 4 4-4 4" /><path d="M20 12H9" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>,
  moon: <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5Z" />,
  globe: <><circle cx="12" cy="12" r="9" /><path d="M3 12h18" /><path d="M12 3c2.5 2.7 3.8 5.7 3.8 9S14.500 18.300 12 21c-2.500-2.700-3.800-5.700-3.800-9S9.500 5.700 12 3Z" /></>,
  link: <><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" /><path d="M14 10a4 4 0 0 0-5.700 0l-3 3a4 4 0 0 0 5.700 5.700l1-1" /></>,
  qr: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><path d="M14 14h3v3M21 14v.01M14 21h3M21 17v4" /></>,
  list: <><path d="M8 6h13M8 12h13M8 18h13" /><path d="M3.500 6h.01M3.500 12h.01M3.500 18h.01" /></>,
  bolt: <path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" />,
  wifi: <><path d="M2 9a15 15 0 0 1 20 0" /><path d="M5 12.500a10 10 0 0 1 14 0" /><path d="M8.500 16a5 5 0 0 1 7 0" /><path d="M12 19.500h.01" /></>,
  alert: <><path d="M12 3 2 20h20L12 3Z" /><path d="M12 10v5" /><path d="M12 18h.01" /></>,
};

export type IconName = keyof typeof P;

export function Icon({ name, size = 18, className, title }: { name: IconName; size?: number; className?: string; title?: string }) {
  return (
    <svg className={`icon${className ? " " + className : ""}`} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden={title ? undefined : true} role={title ? "img" : undefined} focusable="false">
      {title && <title>{title}</title>}
      {P[name]}
    </svg>
  );
}
