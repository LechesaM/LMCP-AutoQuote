import { useEffect, useMemo, useState } from "react";

const TARGETS = [
  { x: 500, y: 300 },
  { x: 80, y: 260 },
  { x: 1450, y: 300 },
];

declare global {
  interface Window {
    __LMCP_HIT_TEST__?: unknown;
  }
}

function describeElement(element: Element | null) {
  if (!element) {
    return null;
  }

  const style = window.getComputedStyle(element);
  const rect = element.getBoundingClientRect();
  return {
    tag: element.tagName.toLowerCase(),
    id: element.id || "",
    className: typeof element.className === "string" ? element.className : "",
    href: element instanceof HTMLAnchorElement ? element.href : "",
    text: (element.textContent || "").trim().slice(0, 120),
    pointerEvents: style.pointerEvents,
    position: style.position,
    zIndex: style.zIndex,
    opacity: style.opacity,
    display: style.display,
    visibility: style.visibility,
    rect: {
      left: Math.round(rect.left),
      top: Math.round(rect.top),
      width: Math.round(rect.width),
      height: Math.round(rect.height),
    },
  };
}

function findViewportCoverCandidates() {
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;

  return Array.from(document.querySelectorAll("body *"))
    .map((element) => {
      const style = window.getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      const coversViewport = rect.left <= 0 && rect.top <= 0 && rect.width >= viewportWidth * 0.9 && rect.height >= viewportHeight * 0.9;
      const fixedOrAbsolute = style.position === "fixed" || style.position === "absolute";
      const visible = style.display !== "none" && style.visibility !== "hidden" && Number.parseFloat(style.opacity || "1") > 0;
      const pointerable = style.pointerEvents !== "none";
      return {
        element,
        coversViewport,
        fixedOrAbsolute,
        visible,
        pointerable,
        zIndex: style.zIndex,
      };
    })
    .filter((entry) => entry.coversViewport && entry.fixedOrAbsolute && entry.visible && entry.pointerable)
    .map((entry) => describeElement(entry.element));
}

export default function DebugHitTestPage() {
  const [report, setReport] = useState(null);

  useEffect(() => {
    const evaluate = () => {
      const hits = TARGETS.map(({ x, y }) => {
        const element = document.elementFromPoint(x, y);
        return {
          x,
          y,
          element: describeElement(element),
        };
      });

      setReport({
        viewport: {
          width: window.innerWidth,
          height: window.innerHeight,
          scrollX: window.scrollX,
          scrollY: window.scrollY,
        },
        hits,
        overlays: findViewportCoverCandidates(),
      });
    };

    const raf = window.requestAnimationFrame(evaluate);
    return () => window.cancelAnimationFrame(raf);
  }, []);

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.__LMCP_HIT_TEST__ = report || null;
    }
  }, [report]);

  const overlaySummary = useMemo(() => {
    if (!report?.overlays?.length) {
      return "No viewport-covering fixed/absolute elements detected.";
    }
    return `${report.overlays.length} candidate overlay/backdrop elements detected.`;
  }, [report]);

  return (
    <div className="space-y-6 px-6 py-8 text-slate-100">
      <div className="glass-card rounded-3xl p-5">
        <div className="text-xs font-black uppercase tracking-[.28em] text-command-cyan">Debug Hit Test</div>
        <h1 className="mt-2 text-3xl font-black text-white">Viewport interaction probe</h1>
        <p className="mt-2 text-sm text-slate-400">
          This hidden page reports the elements returned by <code>document.elementFromPoint</code> and highlights any viewport-covering overlay candidates.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {TARGETS.map(({ x, y }) => {
          const hit = report?.hits?.find((entry) => entry.x === x && entry.y === y)?.element;
          return (
            <div key={`${x}-${y}`} className="glass-card rounded-3xl p-5">
              <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">
                elementFromPoint({x}, {y})
              </div>
              <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-xs text-slate-300">{JSON.stringify(hit || { pending: true }, null, 2)}</pre>
            </div>
          );
        })}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.1fr_.9fr]">
        <div className="glass-card rounded-3xl p-5">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Viewport</div>
          <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-xs text-slate-300">{JSON.stringify(report?.viewport || { pending: true }, null, 2)}</pre>
        </div>

        <div className="glass-card rounded-3xl p-5">
          <div className="text-xs font-black uppercase tracking-[.24em] text-slate-400">Overlay summary</div>
          <div className="mt-2 text-sm text-slate-300">{overlaySummary}</div>
          <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-xs text-slate-300">{JSON.stringify(report?.overlays || [], null, 2)}</pre>
        </div>
      </div>
    </div>
  );
}
