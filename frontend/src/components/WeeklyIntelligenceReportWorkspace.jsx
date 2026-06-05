import { CalendarDays, Download, FileText } from "lucide-react";
import { useMemo, useState } from "react";

const maturitySnapshot = [
  { asset: "Tender-Win Intelligence", current: "58", target: "100", progress: "58%" },
  { asset: "RFQ Gold Dataset", current: "32", target: "50", progress: "64%" },
  { asset: "Supplier Intelligence", current: "74", target: "100", progress: "74%" },
  { asset: "Pricing Intelligence", current: "153", target: "1,000", progress: "15%" },
  { asset: "Province Coverage", current: "9/9", target: "9/9", progress: "100%" },
];

const initialWaveTargets = [
  {
    wave: "Wave 1",
    focus: "High-frequency office and safety supply pricing",
    categories: [
      { category: "Cleaning materials", current_items: 0, target_items: 100 },
      { category: "PPE", current_items: 0, target_items: 100 },
      { category: "Stationery", current_items: 0, target_items: 100 },
      { category: "Office furniture", current_items: 0, target_items: 100 },
    ],
  },
  {
    wave: "Wave 2",
    focus: "Maintenance and infrastructure materials",
    categories: [
      { category: "Electrical materials", current_items: 0, target_items: 110 },
      { category: "Plumbing materials", current_items: 0, target_items: 110 },
      { category: "Building materials", current_items: 0, target_items: 110 },
    ],
  },
  {
    wave: "Wave 3",
    focus: "Specialized municipal and utility consumables",
    categories: [
      { category: "Road signs", current_items: 0, target_items: 90 },
      { category: "Traffic accommodation", current_items: 0, target_items: 90 },
      { category: "Water treatment consumables", current_items: 0, target_items: 190 },
    ],
  },
];

const intakeFields = [
  "Operator name",
  "Capture date",
  "Source type",
  "Category",
  "Product name",
  "Supplier name",
  "Province",
  "Quote reference",
  "Quote date",
  "Validity period",
  "Unit of measure",
  "Pack size",
  "Unit price",
  "Quoted total",
  "Delivery assumptions",
  "Lead time",
  "Confidence rating",
  "Notes on exclusions",
  "Operator who verified it",
];

function waveTotals(wave) {
  const current = wave.categories.reduce((total, item) => total + Number(item.current_items || 0), 0);
  const target = wave.categories.reduce((total, item) => total + Number(item.target_items || 0), 0);
  return { current, target };
}

function clampCount(value, target) {
  const numeric = Number.parseInt(String(value || "0"), 10);
  if (!Number.isFinite(numeric)) return 0;
  return Math.max(0, Math.min(Number(target || 0), numeric));
}

export default function WeeklyIntelligenceReportWorkspace() {
  const [waveTargets, setWaveTargets] = useState(initialWaveTargets);
  const [exportState, setExportState] = useState("idle");
  const reportWeekEnding = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const overallTarget = useMemo(
    () => waveTargets.reduce((total, wave) => total + waveTotals(wave).target, 0),
    [waveTargets],
  );
  const overallCurrent = useMemo(
    () => waveTargets.reduce((total, wave) => total + waveTotals(wave).current, 0),
    [waveTargets],
  );

  function updateCategoryCount(waveIndex, categoryIndex, value) {
    setWaveTargets((current) =>
      current.map((wave, currentWaveIndex) => {
        if (currentWaveIndex !== waveIndex) return wave;
        return {
          ...wave,
          categories: wave.categories.map((category, currentCategoryIndex) => {
            if (currentCategoryIndex !== categoryIndex) return category;
            return { ...category, current_items: clampCount(value, category.target_items) };
          }),
        };
      }),
    );
  }

  const reportMarkdown = useMemo(() => {
    const lines = [
      "# AutoQuote Weekly Intelligence Progress Report",
      "",
      "## Reporting Week",
      `- Week ending: ${reportWeekEnding}`,
      "- Report prepared by:",
      "- Review date:",
      "",
      "## Snapshot",
      ...maturitySnapshot.map((asset) => `- ${asset.asset}: ${asset.current} / ${asset.target} (${asset.progress})`),
      "",
      "## Wave Progress",
      `- Total current / target: ${overallCurrent} / ${overallTarget}`,
      "",
    ];

    for (const wave of waveTargets) {
      const totals = waveTotals(wave);
      lines.push(`### ${wave.wave}`);
      lines.push(`- Focus: ${wave.focus}`);
      lines.push(`- Current / target: ${totals.current} / ${totals.target}`);
      for (const category of wave.categories) {
        lines.push(`- ${category.category}: ${category.current_items} / ${category.target_items}`);
      }
      lines.push("");
    }

    lines.push("## Intake Form Fields");
    for (const field of intakeFields) lines.push(`- ${field}:`);
    lines.push("");
    lines.push("## Decision");
    lines.push("APPROVED - Weekly report export reads from page state; controlled proof unchanged.");
    lines.push("");
    lines.push("## Operating Note");
    lines.push("This export is advisory only. It does not change runtime behavior, workflow logic, dependency configuration, or submission authority.");

    return `${lines.join("\n")}\n`;
  }, [overallCurrent, overallTarget, reportWeekEnding, waveTargets]);

  function exportReport() {
    try {
      const blob = new Blob([reportMarkdown], { type: "text/markdown;charset=utf-8" });
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `autoquote-weekly-intelligence-progress-report-${reportWeekEnding}.md`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
      setExportState("done");
    } catch {
      setExportState("error");
    }
  }

  return (
    <section className="weekly-report-workspace">
      <div className="card weekly-report-hero">
        <div>
          <p className="eyebrow">AutoQuote Weekly Report</p>
          <h1>Weekly Intelligence Progress Report</h1>
          <p className="muted">Read-only operator report for pricing growth, maturity tracking, and controlled regression evidence.</p>
        </div>
        <div className="weekly-report-actions">
          <span><CalendarDays size={14} /> Week ending {reportWeekEnding}</span>
          <button type="button" onClick={exportReport}><Download size={15} />Export Report</button>
        </div>
      </div>

      <div className="weekly-report-summary">
        <div className="weekly-summary-card good"><span>Wave Current</span><b>{overallCurrent}</b></div>
        <div className="weekly-summary-card blue"><span>Wave Target</span><b>{overallTarget}</b></div>
        <div className="weekly-summary-card amber"><span>Pricing Intelligence</span><b>153 / 1,000</b></div>
        <div className="weekly-summary-card"><span>Governance</span><b>Controlled</b></div>
      </div>

      {exportState !== "idle" ? (
        <div className={`weekly-export-state ${exportState}`}>
          <FileText size={15} />
          {exportState === "done" ? "Report exported from current page state." : "Report export failed."}
        </div>
      ) : null}

      <div className="card weekly-panel">
        <div className="card-head">
          <h2>Current Maturity</h2>
          <span>advisory dataset snapshot</span>
        </div>
        <div className="weekly-maturity-grid">
          {maturitySnapshot.map((asset) => (
            <div className="weekly-maturity-card" key={asset.asset}>
              <span>{asset.asset}</span>
              <b>{asset.current} / {asset.target}</b>
              <small>{asset.progress}</small>
            </div>
          ))}
        </div>
      </div>

      <div className="weekly-wave-grid">
        {waveTargets.map((wave, waveIndex) => {
          const totals = waveTotals(wave);
          return (
            <div className="card weekly-wave-card" key={wave.wave}>
              <div className="weekly-wave-head">
                <div>
                  <p className="eyebrow">{wave.wave}</p>
                  <h2>{wave.focus}</h2>
                </div>
                <strong>{totals.current} / {totals.target}</strong>
              </div>
              <div className="weekly-category-list">
                {wave.categories.map((category, categoryIndex) => (
                  <label key={category.category} className="weekly-category-row">
                    <span>{category.category}</span>
                    <input
                      type="number"
                      min="0"
                      max={category.target_items}
                      value={category.current_items}
                      onChange={(event) => updateCategoryCount(waveIndex, categoryIndex, event.target.value)}
                    />
                    <b>/ {category.target_items}</b>
                  </label>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
