const stages = ["Receive", "Parse", "Validate", "Review", "Approve"];

export default function Home() {
  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">Harborline Logistics Demo</p>
        <h1>Ops Intake Agent</h1>
        <p className="lede">
          A governed intake workspace where AI proposes structured data, evidence and issues while
          deterministic policy and a human control every operational write.
        </p>
        <div className="stage-row" aria-label="Workflow stages">
          {stages.map((stage, index) => (
            <div className="stage" key={stage}>
              <span className="stage-number">0{index + 1}</span>
              <span>{stage}</span>
            </div>
          ))}
        </div>
      </section>
      <section className="status-card" aria-labelledby="status-heading">
        <div>
          <p className="eyebrow">M1 platform</p>
          <h2 id="status-heading">Ready for tenant-scoped intake</h2>
          <p>Upload and review surfaces arrive in the next milestone.</p>
        </div>
        <span className="status-pill">Demo shell</span>
      </section>
    </main>
  );
}
