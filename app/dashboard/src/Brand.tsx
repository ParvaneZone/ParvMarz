import logo from "./assets/logo.png";

/** Jinx Data mark. Alpha mask + currentColor-style fill, so it follows light / dark / OLED automatically. */
export function Logo({ size = 40 }: { size?: number }) {
  const u = `url(${logo})`;
  return <span className="brand-logo" role="img" aria-label="Jinx Data" style={{ width: size, height: size, WebkitMaskImage: u, maskImage: u }} />;
}
