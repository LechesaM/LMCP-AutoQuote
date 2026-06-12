import {
  awardConfirmedPromotionProgram,
  businessIntelligenceSchema,
  competitorIntelligenceFields,
  governanceBoundary,
  operatorReadinessPack,
  pricingRecordFields,
  pricingReviewCycles,
  pricingReviewCadence,
  provinceSupplierCoverage,
  priorityCategoryCoverageTarget,
  evidenceReviewFramework,
  trackBOperatingChecklist,
  trackBReviewTemplates,
  trackBAssurance,
  verificationLadder,
  weeklyRegressionRunPrep,
  winProbabilityCalibrationLoop,
  winProbabilityCalibrationFields,
} from "../data/businessIntelligenceExpansionPackV22";

function SectionCard({ title, eyebrow, children, className = "" }) {
  return (
    <section className={`bi-card ${className}`}>
      <div className="bi-card-head">
        <div>
          <div className="bi-eyebrow">{eyebrow}</div>
          <h3>{title}</h3>
        </div>
      </div>
      <div className="bi-card-body">{children}</div>
    </section>
  );
}

function PillList({ items, tone = "neutral" }) {
  return (
    <div className="bi-pill-list">
      {items.map((item) => (
        <span key={item} className={`bi-pill ${tone}`}>
          {item}
        </span>
      ))}
    </div>
  );
}

export default function BusinessIntelligenceExpansionPackPanel() {
  return (
    <section className="bi-pack card">
      <div className="bi-hero">
        <div>
          <p className="eyebrow">Business Intelligence Expansion Pack v2.2</p>
          <h2>Evidence Quality & Traceability Upgrade</h2>
          <p className="muted">
            Focused on intelligence quality, operational readiness, and governance artifacts. No runtime integration is included here.
          </p>
        </div>
        <div className="bi-status">
          <span className="bi-status-chip">Governance boundary preserved</span>
          <span className="bi-status-chip alt">Weekly Regression Run #2 prep only</span>
        </div>
      </div>

      <div className="bi-grid">
        <SectionCard eyebrow="Record schema" title="Required fields on every intelligence record">
          <PillList items={businessIntelligenceSchema} tone="teal" />
        </SectionCard>

        <SectionCard eyebrow="Verification ladder" title="Promotion path for tender intelligence">
          <div className="bi-flow">
            {verificationLadder.map((step) => (
              <div key={`${step.from}-${step.to}`} className="bi-flow-step">
                <strong>
                  {step.from} → {step.to}
                </strong>
                <span>{step.intent}</span>
              </div>
            ))}
          </div>
        </SectionCard>

        <SectionCard eyebrow="Review framework" title="Evidence quality improvement loop">
          <div className="bi-flow">
            {evidenceReviewFramework.map((step) => (
              <div key={step.step} className="bi-flow-step">
                <strong>{step.step}</strong>
                <span>{step.rule}</span>
              </div>
            ))}
          </div>
        </SectionCard>

        <SectionCard eyebrow="Track B" title="Increase Award Confirmed tender-win records">
          <PillList items={awardConfirmedPromotionProgram} tone="teal" />
        </SectionCard>

        <SectionCard eyebrow="Province coverage" title="Supplier gap closure template" className="wide">
          <div className="bi-table-wrap">
            <table className="bi-table">
              <thead>
                <tr>
                  <th>Province</th>
                  <th>Category</th>
                  <th>Primary Supplier</th>
                  <th>Backup Supplier</th>
                  <th>Coverage Status</th>
                </tr>
              </thead>
              <tbody>
                {provinceSupplierCoverage.map((row) => (
                  <tr key={`${row.province}-${row.category}`}>
                    <td>{row.province}</td>
                    <td>{row.category}</td>
                    <td>{row.primary}</td>
                    <td>{row.backup}</td>
                    <td>{row.coverage}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>

        <SectionCard eyebrow="Coverage target" title="Priority category closure criteria">
          <PillList items={priorityCategoryCoverageTarget} tone="amber" />
        </SectionCard>

        <SectionCard eyebrow="Pricing quality" title="Review cycle by volatility">
          <div className="bi-stack">
            {pricingReviewCycles.map((row) => (
              <div key={row.status} className="bi-stack-row">
                <strong>{row.status}</strong>
                <span>{row.cadence}</span>
                <small>{row.reason}</small>
              </div>
            ))}
          </div>
        </SectionCard>

        <SectionCard eyebrow="Pricing records" title="Fields to add to all pricing records">
          <PillList items={pricingRecordFields} tone="blue" />
        </SectionCard>

        <SectionCard eyebrow="Cadence" title="Formal 30 / 90 / 180-day review cadence">
          <div className="bi-stack">
            {pricingReviewCadence.map((row) => (
              <div key={row.cadence} className="bi-stack-row">
                <strong>{row.cadence}</strong>
                <small>{row.trigger}</small>
              </div>
            ))}
          </div>
        </SectionCard>

        <SectionCard eyebrow="Competitor intelligence" title="Signals to track">
          <PillList items={competitorIntelligenceFields} tone="amber" />
        </SectionCard>

        <SectionCard eyebrow="Calibration" title="Win probability comparison">
          <PillList items={winProbabilityCalibrationFields} tone="blue" />
        </SectionCard>

        <SectionCard eyebrow="Calibration loop" title="Actual outcome feedback cycle">
          <PillList items={winProbabilityCalibrationLoop} tone="teal" />
        </SectionCard>

        <SectionCard eyebrow="Operator readiness" title="Readiness pack">
          <PillList items={operatorReadinessPack} tone="rose" />
        </SectionCard>

        <SectionCard eyebrow="Regression prep" title="Weekly Regression Run #2 artifacts">
          <PillList items={weeklyRegressionRunPrep} tone="neutral" />
        </SectionCard>

        <SectionCard eyebrow="Boundary" title="Things not to do" className="wide">
          <PillList items={governanceBoundary} tone="danger" />
        </SectionCard>

        <SectionCard eyebrow="Track B assurance" title="Certification and regression safeguards" className="wide">
          <PillList items={trackBAssurance} tone="rose" />
        </SectionCard>

        <SectionCard eyebrow="Track B checklist" title="Operational sequence for governance updates">
          <PillList items={trackBOperatingChecklist} tone="teal" />
        </SectionCard>

        <SectionCard eyebrow="Templates" title="Review templates to keep on hand">
          <PillList items={trackBReviewTemplates} tone="amber" />
        </SectionCard>
      </div>
    </section>
  );
}
