/**
 * The woven mark from docs/logo, redrawn as SVG so it stays crisp and takes its colours
 * from CSS: --mark-warp (vertical threads), --mark-weft (horizontal threads), and
 * --mark-gap (the ground showing between threads where one passes over the other).
 *
 * `tile` sets the mark on its app-icon tile (filled with --mark-gap), as the favicon and the
 * icon sheet show it. The tile is the mark's size / 0.7, so the threads keep the sheet's margin.
 */
export function LoomMark({
  size = 24,
  tile = false,
}: {
  size?: number;
  tile?: boolean;
}) {
  return (
    <svg
      className="loom-mark"
      width={size}
      height={size}
      viewBox={tile ? "-48 -48 320 320" : "-6 -6 236 236"}
      aria-hidden="true"
      focusable="false"
    >
      {tile && (
        <rect
          x="-48"
          y="-48"
          width="320"
          height="320"
          rx="70"
          fill="var(--mark-gap)"
        />
      )}
      <g fill="var(--mark-weft)">
        <rect y="42" width="224" height="28" rx="14" />
        <rect y="98" width="224" height="28" rx="14" />
        <rect y="154" width="224" height="28" rx="14" />
      </g>
      <g stroke="var(--mark-gap)" strokeWidth="8">
        <g fill="var(--mark-warp)">
          <rect x="42" width="28" height="224" rx="14" />
          <rect x="98" width="28" height="224" rx="14" />
          <rect x="154" width="28" height="224" rx="14" />
        </g>
        {/* Where the weft passes over the warp: top and bottom rows over the centre thread, the middle row over the outer two. */}
        <g fill="var(--mark-weft)">
          <rect x="92" y="42" width="40" height="28" />
          <rect x="92" y="154" width="40" height="28" />
          <rect x="36" y="98" width="40" height="28" />
          <rect x="148" y="98" width="40" height="28" />
        </g>
      </g>
    </svg>
  );
}
