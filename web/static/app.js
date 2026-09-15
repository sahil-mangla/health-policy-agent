"use strict";

/* The analysis view. Every label and state shown here comes from the API,
   which takes them from decoder.respond.labels — the browser never decides
   how strongly something is supported, it only lays out what resolve()
   already decided.

   The per-state explanatory copy below is the "required accompanying
   content" column of §8's UI mapping table. It is specific to the state it
   explains; §8 forbids a generic "AI can make mistakes" banner, so there
   is deliberately no such banner anywhere on this page. */

const STATE_MEANING = {
  WELL_SUPPORTED:
    "Found stated in your document. The exact words it was checked against are below.",
  NEEDS_CONFIRMATION:
    "The document points this way, but the wording is not decisive on its own. " +
    "Confirm it with your insurer before you rely on it.",
  NEEDS_INFORMATION:
    "This depends on something we do not have. It is named below, and the answer " +
    "changes once you supply it.",
  INSUFFICIENT_EVIDENCE:
    "We searched the clauses retrieved from your document and did not find this stated. " +
    "That is not the same as the policy denying it — ask your insurer directly.",
  CONFLICTING:
    "Your documents disagree. Both passages are shown below with the document each " +
    "came from; the policy wording governs over a summary, but the disagreement itself " +
    "is worth raising.",
};

const EXAMPLE_QUESTIONS = [
  "What co-payment applies to my claim?",
  "What is the room rent limit per day?",
  "How long is the waiting period for pre-existing diseases?",
  "Does my policy cover dental implants for cosmetic reasons?",
];

const el = (id) => document.getElementById(id);
const POLL_MS = 400;

let documents = [];

async function init() {
  const res = await fetch("/api/documents");
  documents = await res.json();

  const select = el("doc-select");
  select.innerHTML = "";
  for (const doc of documents) {
    const option = document.createElement("option");
    option.value = doc.doc_id;
    option.textContent = `${doc.insurer} — ${doc.product}`;
    select.appendChild(option);
  }
  select.addEventListener("change", showDocNote);
  showDocNote();

  const examples = el("examples");
  for (const question of EXAMPLE_QUESTIONS) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "example-chip";
    chip.textContent = question;
    chip.addEventListener("click", () => {
      el("situation").value = question;
    });
    examples.appendChild(chip);
  }

  el("analyze").addEventListener("click", analyse);
  el("dialog-close").addEventListener("click", () => el("evidence-dialog").close());

  const heroInputs = await fetch("/api/room-rent-inputs").then((r) => r.json());
  el("room-tariff-note").textContent = heroInputs.room_tariff_per_day.description;
  el("sum-insured-note").textContent = heroInputs.sum_insured.description;
}

function showDocNote() {
  const doc = documents.find((d) => d.doc_id === el("doc-select").value);
  el("doc-note").textContent = doc ? doc.note : "";
}

async function analyse() {
  const situation = el("situation").value.trim();
  if (!situation) {
    showError("Tell us what you want to know about this policy first.");
    return;
  }

  el("error-panel").hidden = true;
  el("results").hidden = true;
  el("progress-panel").hidden = false;
  el("analyze").disabled = true;
  setProgress({ detail: "Starting", completed: 0, total: 0 });

  try {
    const body = { doc_id: el("doc-select").value, situation };
    const roomTariff = parseFloat(el("room-tariff").value);
    const sumInsured = parseFloat(el("sum-insured").value);
    if (Number.isFinite(roomTariff) && roomTariff > 0) body.room_tariff_per_day = roomTariff;
    if (Number.isFinite(sumInsured) && sumInsured > 0) body.sum_insured = sumInsured;

    const started = await postJSON("/api/analyze", body);
    const job = await pollUntilDone(started.job_id);
    if (job.status === "failed") {
      showError(`The analysis could not finish (${job.error}).`);
    } else {
      render(job.answer);
    }
  } catch (err) {
    showError(String(err.message || err));
  } finally {
    el("progress-panel").hidden = true;
    el("analyze").disabled = false;
  }
}

async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

async function pollUntilDone(jobId) {
  for (;;) {
    const res = await fetch(`/api/jobs/${jobId}`);
    if (!res.ok) throw new Error("Lost track of this analysis.");
    const job = await res.json();
    setProgress(job.progress);
    if (job.status !== "running") return job;
    await new Promise((resolve) => setTimeout(resolve, POLL_MS));
  }
}

function setProgress(progress) {
  el("progress-detail").textContent = progress.detail || "Working";
  const pct = progress.total > 0 ? (progress.completed / progress.total) * 100 : 8;
  el("progress-bar").style.width = `${pct}%`;
  el("progress-note").textContent =
    progress.total > 0
      ? `Checking claim ${Math.min(progress.completed + 1, progress.total)} of ${progress.total}. ` +
        "Each one is checked against every clause we retrieved, separately."
      : "";
}

function showError(message) {
  const panel = el("error-panel");
  panel.textContent = message;
  panel.hidden = false;
}

function render(answer) {
  el("results").hidden = false;

  const chip = el("overall-chip");
  chip.textContent = answer.overall_label;
  chip.className = `state-chip state-${answer.overall_state}`;
  chip.dataset.state = answer.overall_state;
  el("overall-explainer").textContent = STATE_MEANING[answer.overall_state] || "";

  renderArithmetic(answer.room_rent_calculation);

  const claims = el("claims");
  claims.innerHTML = "";
  for (const claim of answer.claims) {
    claims.appendChild(renderClaim(claim));
  }
  el("claims-panel").hidden = answer.claims.length === 0;

  const questions = el("questions");
  questions.innerHTML = "";
  for (const question of answer.questions) {
    const li = document.createElement("li");
    li.textContent = question;
    questions.appendChild(li);
  }
  el("questions-panel").hidden = answer.questions.length === 0;

  const inputs = el("missing-inputs");
  inputs.innerHTML = "";
  for (const input of answer.missing_inputs) {
    const li = document.createElement("li");
    const name = document.createElement("span");
    name.className = "input-name";
    name.textContent = input.name;
    li.appendChild(name);
    li.appendChild(document.createTextNode(` — ${input.description}`));
    inputs.appendChild(li);
  }
  el("inputs-panel").hidden = answer.missing_inputs.length === 0;
}

function renderArithmetic(calc) {
  const panel = el("arithmetic-panel");
  if (!calc) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;

  const rupees = (value) => `₹${Math.round(value).toLocaleString("en-IN")}`;
  const cells = [
    ["Eligible limit", `${rupees(calc.eligible_limit_per_day)}/day`, null],
  ];
  if (calc.room_tariff_per_day != null) {
    cells.push(["Your room tariff", `${rupees(calc.room_tariff_per_day)}/day`, null]);
    cells.push([
      calc.exceeds_limit ? "Exceeds limit by" : "Within limit by",
      rupees(Math.abs(calc.room_tariff_per_day - calc.eligible_limit_per_day)),
      calc.exceeds_limit ? "exceeds" : "within",
    ]);
  }
  if (calc.deduction_ratio_percent != null) {
    cells.push([
      "Associated expenses payable",
      `${calc.deduction_ratio_percent.toFixed(1)}%`,
      "exceeds",
    ]);
  }

  const grid = el("arithmetic-grid");
  grid.innerHTML = "";
  for (const [label, value, cls] of cells) {
    const cell = document.createElement("div");
    if (cls) cell.className = cls;
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    cell.append(dt, dd);
    grid.appendChild(cell);
  }
}

function renderClaim(claim) {
  const li = document.createElement("li");
  li.className = `claim s-${claim.state}`;
  li.dataset.state = claim.state;

  const head = document.createElement("button");
  head.type = "button";
  head.className = "claim-head";
  head.setAttribute("aria-expanded", "false");

  const chip = document.createElement("span");
  chip.className = `state-chip state-${claim.state}`;
  chip.textContent = claim.label;

  const text = document.createElement("span");
  text.className = "claim-text";
  text.textContent = claim.text;

  const disclosure = document.createElement("span");
  disclosure.className = "disclosure";
  disclosure.textContent = "Why ▾";

  head.append(chip, text, disclosure);

  const body = document.createElement("div");
  body.className = "claim-body";
  body.hidden = true;

  const why = document.createElement("p");
  why.className = "why";
  why.textContent = STATE_MEANING[claim.state] || "";
  body.appendChild(why);

  if (claim.evidence.length > 0) {
    body.appendChild(renderEvidence(claim.evidence));
  }

  head.addEventListener("click", () => {
    body.hidden = !body.hidden;
    head.setAttribute("aria-expanded", String(!body.hidden));
    disclosure.textContent = body.hidden ? "Why ▾" : "Why ▴";
  });

  li.append(head, body);
  return li;
}

function renderEvidence(evidence) {
  const list = document.createElement("ul");
  list.className = "evidence";

  for (const item of evidence) {
    const li = document.createElement("li");
    li.className = `evidence-item ${item.verdict === "CONTRADICTS" ? "contradicts" : ""}`;

    const verdict = document.createElement("div");
    verdict.className = "evidence-verdict";
    verdict.textContent = item.verdict === "CONTRADICTS" ? "Contradicted by" : "Supported by";

    // Verbatim source text, never paraphrased: §9.4 forbids translating or
    // rewriting quoted clause text, and §8 forbids a citation that is only
    // a section number.
    const quote = document.createElement("blockquote");
    quote.className = "evidence-quote";
    quote.textContent = `“${item.quote}”`;

    const source = document.createElement("button");
    source.type = "button";
    source.className = "evidence-source";
    source.textContent = `${item.doc_id}, page ${item.page} — show me on the page`;
    source.addEventListener("click", () => openEvidence(item));

    li.append(verdict, quote, source);
    list.appendChild(li);
  }
  return list;
}

async function openEvidence(item) {
  el("dialog-title").textContent = "Where this came from";
  el("dialog-source").textContent = `${item.doc_id} — page ${item.page}`;
  el("dialog-quote").textContent = `“${item.quote}”`;

  const img = el("page-image");
  img.alt = `Page ${item.page} of ${item.doc_id} with the cited passage highlighted`;
  img.removeAttribute("src");
  el("evidence-dialog").showModal();

  const url = `/api/page-image/${encodeURIComponent(item.doc_id)}/${item.page}?bbox=${encodeURIComponent(item.bbox)}`;
  const res = await fetch(url);
  if (!res.ok) return;

  // Fetched rather than set directly on src so the highlight's position
  // can be read off the response header and scrolled to — a reader who
  // opens this to see one passage should not have to find it.
  const fraction = parseFloat(res.headers.get("X-Highlight-Fraction"));
  const blobUrl = URL.createObjectURL(await res.blob());
  img.addEventListener(
    "load",
    () => {
      URL.revokeObjectURL(blobUrl);
      if (Number.isFinite(fraction)) scrollToHighlight(img, fraction);
    },
    { once: true }
  );
  img.src = blobUrl;
}

function scrollToHighlight(img, fraction) {
  const dialog = el("evidence-dialog");
  // The pinned head and quote cover the top of the dialog, so the
  // highlight is centred in what is actually visible below them, not in
  // the dialog box as a whole.
  const pinned = document.querySelector(".dialog-sticky").offsetHeight;
  const visible = dialog.clientHeight - pinned;
  const target = img.offsetTop + img.clientHeight * fraction - pinned - visible / 2;
  dialog.scrollTo({ top: Math.max(0, target), behavior: "smooth" });
}

init();
