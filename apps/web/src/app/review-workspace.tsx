"use client";

import { useMemo, useState } from "react";

type Fixture = "valid" | "missing" | "conflict";
type Status = "extracted" | "conflicting" | "operator_corrected";

type Evidence = { id: string; excerpt: string };
type Field = {
  path: string;
  value: string;
  original: string;
  status: Status;
  evidence: Evidence[];
};

const sourceText =
  "CUSTOMER ACCT-A   REFERENCE REQ-A-100\nORIGIN ORIGIN-A   SHIP DATE 2026-09-12\nDESTINATION US 02110\nSERVICE STANDARD\nSKU-100 / QTY 2 / EA";

const baseFields: Field[] = [
  { path: "customer_account_code", value: "ACCT-A", original: "ACCT-A", status: "extracted", evidence: [{ id: "ev-customer", excerpt: "ACCT-A" }] },
  { path: "external_request_reference", value: "REQ-A-100", original: "REQ-A-100", status: "extracted", evidence: [{ id: "ev-reference", excerpt: "REQ-A-100" }] },
  { path: "requested_ship_date", value: "2026-09-12", original: "2026-09-12", status: "extracted", evidence: [{ id: "ev-date", excerpt: "2026-09-12" }] },
  { path: "destination.postal_code", value: "02110", original: "02110", status: "extracted", evidence: [{ id: "ev-postal", excerpt: "02110" }] },
  { path: "service_level", value: "STANDARD", original: "STANDARD", status: "extracted", evidence: [{ id: "ev-service", excerpt: "STANDARD" }] },
  { path: "line_items[0].quantity", value: "2", original: "2", status: "extracted", evidence: [{ id: "ev-quantity", excerpt: "QTY 2" }] },
];

const queue = [
  { id: "intake-8c1f", ref: "REQ-A-100", status: "review", issue: "1 warning", fixture: "valid" as Fixture },
  { id: "intake-7b22", ref: "REQ-A-101", status: "review", issue: "1 blocking", fixture: "missing" as Fixture },
  { id: "intake-6d09", ref: "REQ-A-099", status: "processing", issue: "—", fixture: "conflict" as Fixture },
];

function shortHash(value: string) {
  let hash = 0;
  for (const character of value) hash = (hash * 31 + character.charCodeAt(0)) | 0;
  return Math.abs(hash).toString(16).padStart(8, "0").slice(0, 8);
}

export default function ReviewWorkspace() {
  const [activeFixture, setActiveFixture] = useState<Fixture>("valid");
  const [fields, setFields] = useState<Field[]>(baseFields);
  const [selectedPath, setSelectedPath] = useState("line_items[0].quantity");
  const [draftValue, setDraftValue] = useState("2");
  const [reviewVersion, setReviewVersion] = useState(2);
  const [warningAcknowledged, setWarningAcknowledged] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const selectedField = fields.find((field) => field.path === selectedPath) ?? fields[0];
  const blocking = activeFixture === "missing";
  const conflict = activeFixture === "conflict" && !warningAcknowledged;
  const canPreview = !blocking && !conflict;
  const activeEvidence = selectedField.evidence[0]?.excerpt ?? "No verified excerpt";

  const issue = useMemo(() => {
    if (blocking) {
      return { severity: "blocking", code: "DESTINATION_POSTAL_REQUIRED", message: "Destination postal code is missing from the normalized draft." };
    }
    if (conflict) {
      return { severity: "warning", code: "CONFLICTING_EVIDENCE", message: "Two source references disagree. A reviewer must acknowledge the selected value." };
    }
    return null;
  }, [blocking, conflict]);

  function openFixture(fixture: Fixture) {
    const nextFields = baseFields.map((field) => ({ ...field, evidence: [...field.evidence] }));
    if (fixture === "missing") {
      const postal = nextFields.find((field) => field.path === "destination.postal_code");
      if (postal) { postal.value = ""; postal.original = "Missing"; postal.status = "conflicting"; }
    }
    if (fixture === "conflict") {
      const reference = nextFields.find((field) => field.path === "external_request_reference");
      if (reference) {
        reference.status = "conflicting";
        reference.evidence = [{ id: "ev-reference", excerpt: "REQ-A-100" }, { id: "ev-reference-alt", excerpt: "REQ-A-101" }];
      }
    }
    setActiveFixture(fixture);
    setFields(nextFields);
    setSelectedPath(fixture === "missing" ? "destination.postal_code" : "line_items[0].quantity");
    setDraftValue(fixture === "missing" ? "" : "2");
    setReviewVersion(1);
    setWarningAcknowledged(false);
    setPreview(null);
  }

  function saveField() {
    if (!draftValue.trim()) return;
    setFields((current) => current.map((field) => field.path === selectedPath ? { ...field, value: draftValue.trim(), status: "operator_corrected" } : field));
    setReviewVersion((version) => version + 1);
    setPreview(null);
  }

  function makePreview() {
    if (!canPreview) return;
    const material = `${activeFixture}:${reviewVersion}:${fields.map((field) => `${field.path}=${field.value}`).join("|")}`;
    setPreview(shortHash(material));
  }

  return (
    <main className="app-frame">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">OI</div>
          <div><div className="brand-name">Ops Intake / Control Desk</div><div className="brand-subtitle">Harborline Logistics · Tenant A · synthetic workspace</div></div>
        </div>
        <div className="environment-pill">Provider-free demo</div>
      </header>

      <section className="workspace" aria-labelledby="workspace-title">
        <div className="workspace-heading">
          <div>
            <p className="eyebrow">M8 review workspace</p>
            <h1 id="workspace-title">Make the evidence earn its way through.</h1>
            <p className="heading-copy">Every normalized value stays tied to a verified excerpt. Edits create a new draft version; the preview disappears until deterministic checks run again.</p>
          </div>
          <div className="heading-meta"><strong>v{reviewVersion}</strong>review version / optimistic lock</div>
        </div>

        <div className="queue-strip" aria-label="Synthetic intake queue">
          {queue.map((item) => <button className="queue-card" key={item.id} aria-pressed={activeFixture === item.fixture} onClick={() => openFixture(item.fixture)} type="button"><span className="queue-card-top"><span className="queue-card-title">{item.id}</span><span className={`status-badge ${item.status}`}>{item.status}</span></span><span className="queue-card-ref">{item.ref} · {item.issue}</span></button>)}
        </div>

        <div className="review-grid">
          <section className="panel source-panel" aria-labelledby="source-title">
            <div className="panel-header"><div><div className="panel-kicker">01 / source</div><h2 className="panel-title" id="source-title">Document trace</h2></div><span className="status-badge">escaped</span></div>
            <div className="source-card"><div className="source-toolbar"><span className="source-file">request.txt</span><span>text · sha256 verified</span></div><div className="source-body" aria-label="Synthetic source text">{sourceText.split(activeEvidence).map((part, index, all) => <span key={`${part}-${index}`}>{part}{index < all.length - 1 ? <mark>{activeEvidence}</mark> : null}</span>)}</div></div>
            <p className="source-note">Source and model text are untrusted data. This view renders it as text and never treats it as instructions.</p>
            <div className="trace-rail"><strong>Evidence selected</strong><span>{selectedField.path} · {selectedField.evidence[0]?.id ?? "none"}</span></div>
          </section>

          <section className="panel fields-panel" aria-labelledby="fields-title">
            <div className="panel-header"><div><div className="panel-kicker">02 / normalized draft</div><h2 className="panel-title" id="fields-title">Canonical fields</h2></div><span className="status-badge review">reviewer</span></div>
            <ul className="field-list">{fields.map((field) => <li key={field.path}><button className="field-button" aria-pressed={field.path === selectedPath} onClick={() => { setSelectedPath(field.path); setDraftValue(field.value); }} type="button"><span><span className="field-path">{field.path}</span><span className="field-value">{field.value || "Missing"}</span></span><span className={`field-status ${field.status}`}>{field.status.replace("_", " ")}</span></button></li>)}</ul>
            <div className="selected-field"><label htmlFor="field-value">Edit selected field</label><input id="field-value" value={draftValue} onChange={(event) => setDraftValue(event.target.value)} /><p className="selected-field-meta">Original: <strong>{selectedField.original || "Missing"}</strong><br />Evidence: <span className="evidence-link">{selectedField.evidence.map((evidence) => evidence.id).join(", ")}</span></p><div className="button-row"><button className="button" onClick={saveField} type="button">Save correction</button><button className="button secondary" onClick={() => setDraftValue(selectedField.value)} type="button">Reset</button></div></div>
          </section>

          <section className="panel issues-panel" aria-labelledby="issues-title">
            <div className="panel-header"><div><div className="panel-kicker">03 / policy gate</div><h2 className="panel-title" id="issues-title">Issues & rules</h2></div><span className="status-badge">deterministic</span></div>
            {issue ? <div className={`issue-card ${issue.severity}`}><div className="issue-top"><span className="issue-code">{issue.code}</span><span className="issue-severity">{issue.severity}</span></div><p>{issue.message}</p>{issue.severity === "warning" ? <button className="button secondary" onClick={() => { setWarningAcknowledged(true); setReviewVersion((version) => version + 1); setPreview(null); }} type="button">Acknowledge warning</button> : <span className="safe-note">Resolve the field with evidence before preview.</span>}</div> : <div className="issue-card"><div className="issue-code">NO_ACTIVE_ISSUES</div><p>Required fields and tenant policy checks are clear.</p></div>}
            <div className="rule-card"><span className="rule-ref">sop:harborline:fulfillment:1 · effective 2026-01-01</span><h3>Harborline fulfillment intake policy</h3><p>Active customers, authorized origins, supported service levels and complete line items are required.</p></div>
            <button className="button secondary" onClick={() => { setReviewVersion((version) => version + 1); setPreview(null); }} type="button">Revalidate draft</button>
            <div className="preview-card"><div className="panel-kicker">Action preview</div><h3>Draft fulfillment request</h3><p>Immutable payload bound to the current draft, validation and review version.</p><div className="hash-line">payload hash · {preview ?? "not created"}<br />review version · {reviewVersion}</div><button className="button" disabled={!canPreview} onClick={makePreview} type="button">{preview ? "Preview created" : "Create immutable preview"}</button>{preview ? <p className="preview-created">Preview ready for explicit approval · no write performed.</p> : null}</div>
            <p className="safe-note">The demo has no operational credentials. Approval and guarded execution are separate controls.</p>
          </section>
        </div>
      </section>
    </main>
  );
}
