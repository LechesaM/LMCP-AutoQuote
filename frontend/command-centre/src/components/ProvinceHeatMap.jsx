import { provinceDistribution } from "../data/harvestedRfqs";
import { heatColor } from "../utils/provinceStats";
import StateBadge from "./ui/StateBadge.tsx";
import { SkeletonCard } from "./ui/SkeletonBlocks.tsx";

const shapes = [
  { code: "NC", x: 70, y: 160, w: 190, h: 165, rx: 36 },
  { code: "WC", x: 130, y: 340, w: 120, h: 92, rx: 30 },
  { code: "EC", x: 270, y: 330, w: 150, h: 86, rx: 28 },
  { code: "FS", x: 310, y: 225, w: 120, h: 100, rx: 30 },
  { code: "NW", x: 260, y: 130, w: 110, h: 85, rx: 28 },
  { code: "GP", x: 390, y: 150, w: 72, h: 62, rx: 22 },
  { code: "LP", x: 390, y: 50, w: 130, h: 88, rx: 30 },
  { code: "MP", x: 470, y: 145, w: 102, h: 88, rx: 28 },
  { code: "KZN", x: 470, y: 265, w: 108, h: 112, rx: 30 },
];

const off = {
  NC: [22, 78],
  WC: [26, 50],
  EC: [34, 48],
  FS: [33, 56],
  NW: [28, 48],
  GP: [17, 38],
  LP: [40, 50],
  MP: [30, 52],
  KZN: [28, 60],
};

function byCode(code) {
  return provinceDistribution.find((row) => row.code === code);
}

export default function ProvinceHeatMap({ state = "ready", onRetry }) {
  if (state === "loading") {
    return (
      <div className="glass-card relative min-h-[560px] overflow-hidden rounded-3xl p-6">
        <SkeletonCard lines={6} />
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className="glass-card min-h-[560px] rounded-3xl p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-black text-white">South Africa RFQ Heat Map</h2>
            <p className="mt-1 text-sm text-slate-400">Unable to load telemetry.</p>
          </div>
          <StateBadge state="error" />
        </div>
        {onRetry ? (
          <button
            onClick={onRetry}
            className="mt-4 rounded-2xl border border-command-cyan/40 bg-command-cyan/10 px-4 py-2 text-sm font-bold text-command-cyan"
          >
            Retry
          </button>
        ) : null}
      </div>
    );
  }

  const provinces = state === "empty" ? [] : provinceDistribution;

  return (
    <div className={`glass-card relative min-h-[560px] overflow-hidden rounded-3xl p-6 ${state === "stale" ? "opacity-85" : ""}`}>
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-black text-white">South Africa RFQ Heat Map</h2>
          <p className="mt-1 text-sm text-slate-400">Eligible RFQ intensity by province and estimated value.</p>
        </div>
        <StateBadge state={state === "refreshing" ? "refreshing" : state === "stale" ? "stale" : "ready"} />
      </div>

      {provinces.length ? (
        <>
          <div className="relative mx-auto h-[430px] max-w-[680px]">
            <svg viewBox="0 0 650 480" className="h-full w-full animate-mapPulse">
              <defs>
                <filter id="hotGlow">
                  <feGaussianBlur stdDeviation="5" result="coloredBlur" />
                  <feMerge>
                    <feMergeNode in="coloredBlur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>
              <path
                d="M85 170 C120 75 265 58 360 78 C458 40 552 90 585 184 C638 322 506 414 388 425 C270 460 124 438 70 330 C42 272 52 220 85 170Z"
                fill="rgba(15,23,42,.62)"
                stroke="rgba(148,163,184,.28)"
                strokeWidth="2"
              />
              {shapes.map((shape) => {
                const province = byCode(shape.code);
                if (!province) {
                  return null;
                }
                const color = heatColor(province);
                const [lx, ly] = off[shape.code];
                const opacity = Math.max(0.38, province.eligible / 170);

                return (
                  <g key={shape.code}>
                    <rect
                      className="map-province"
                      x={shape.x}
                      y={shape.y}
                      width={shape.w}
                      height={shape.h}
                      rx={shape.rx}
                      fill={color}
                      opacity={opacity}
                      stroke="rgba(255,255,255,.32)"
                      strokeWidth="1.4"
                      filter={province.code === "GP" ? "url(#hotGlow)" : undefined}
                    />
                    <text x={shape.x + lx} y={shape.y + ly} fill="#e5f7ef" fontSize="19" fontWeight="900">
                      {shape.code}
                    </text>
                    <text x={shape.x + lx} y={shape.y + ly + 21} fill="#dbeafe" fontSize="12" fontWeight="700">
                      {province.eligible} eligible
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {provinces.slice(0, 6).map((province) => (
              <div key={province.province} className="rounded-2xl border border-slate-700/60 bg-slate-950/45 p-3">
                <div className="text-sm font-bold text-white">{province.province}</div>
                <div className="mt-1 text-xs text-slate-400">{province.rfqs} RFQs · {province.eligible} eligible</div>
                <div className="mt-2 flex items-center justify-between text-xs">
                  <span className="text-command-cyan">R{province.value}M</span>
                  <span className="text-command-green">{province.avgMargin}% margin</span>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-5 flex items-center gap-3">
            <span className="text-xs font-semibold uppercase tracking-[.22em] text-slate-500">Low</span>
            <div className="h-3 flex-1 rounded-full bg-gradient-to-r from-sky-400 via-command-green via-yellow-400 via-orange-500 to-red-500" />
            <span className="text-xs font-semibold uppercase tracking-[.22em] text-slate-500">High</span>
          </div>
        </>
      ) : (
        <div className="mt-8 rounded-3xl border border-dashed border-slate-700/70 bg-slate-950/40 p-8 text-center text-slate-400">
          No province telemetry available.
        </div>
      )}
    </div>
  );
}
