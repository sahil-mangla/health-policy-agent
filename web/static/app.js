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
// §8's UI-mapping table: a NEEDS_INFORMATION claim must "name the missing
// input, offer to accept it." Accumulates what the reader has supplied via
// the missing-inputs form across re-checks of the SAME situation; reset
// whenever a fresh "Analyse" click starts a genuinely new question.
let extraProvidedInputs = {};
// Every per-piece translator created while rendering the current answer
// (overall summary, each claim, each question) — the global "Translate
// everything" toggle just runs all of them, rather than duplicating the
// translation logic itself. Reset on every fresh render().
let translateAllTargets = [];

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

  el("analyze").addEventListener("click", () => {
    extraProvidedInputs = {};
    analyse();
  });
  el("dialog-close").addEventListener("click", () => el("evidence-dialog").close());

  el("missing-inputs-form").addEventListener("submit", (event) => {
    event.preventDefault();
    for (const [name, value] of new FormData(event.target).entries()) {
      if (value) extraProvidedInputs[String(name)] = String(value);
    }
    analyse();
  });

  setupUpload();
  setupTranslateAll();

  const heroInputs = await fetch("/api/room-rent-inputs").then((r) => r.json());
  el("room-tariff-note").textContent = heroInputs.room_tariff_per_day.description;
  el("sum-insured-note").textContent = heroInputs.sum_insured.description;
}

function setupUpload() {
  el("upload-input").addEventListener("change", async (event) => {
    const input = /** @type {HTMLInputElement} */ (event.target);
    const file = input.files && input.files[0];
    if (!file) return;

    const status = el("upload-status");
    status.hidden = false;
    status.className = "upload-status";
    status.textContent = "Uploading…";

    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch("/api/upload", { method: "POST", body: formData });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `Upload failed (${res.status})`);

      const option = document.createElement("option");
      option.value = data.doc_id;
      option.textContent = `Your upload — ${data.filename}`;
      el("doc-select").appendChild(option);
      el("doc-select").value = data.doc_id;
      documents.push({
        doc_id: data.doc_id,
        insurer: "Your upload",
        product: data.filename,
        note: "Not stored beyond this session.",
      });
      showDocNote();

      status.className = "upload-status ok";
      status.textContent = `Uploaded "${data.filename}" — selected above.`;
    } catch (err) {
      status.className = "upload-status error";
      status.textContent = String(err.message || err);
    } finally {
      input.value = "";
    }
  });
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
    const body = { doc_id: el("doc-select").value, situation, provided_inputs: extraProvidedInputs };
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
  translateAllTargets = [];

  const chip = el("overall-chip");
  chip.textContent = answer.overall_label;
  chip.className = `state-chip state-${answer.overall_state}`;
  chip.dataset.state = answer.overall_state;
  const overallExplanation = STATE_MEANING[answer.overall_state] || "";
  el("overall-explainer").textContent = overallExplanation;

  const overallHindi = el("overall-hindi");
  overallHindi.innerHTML = "";
  const overallTranslator = createTranslator(() => overallExplanation, { showButton: false });
  overallHindi.appendChild(overallTranslator.element);
  translateAllTargets.push(overallTranslator.translate);

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
    const text = document.createElement("span");
    text.textContent = question;
    li.appendChild(text);
    const questionTranslator = createTranslator(() => question);
    li.appendChild(questionTranslator.element);
    translateAllTargets.push(questionTranslator.translate);
    questions.appendChild(li);
  }
  el("questions-panel").hidden = answer.questions.length === 0;

  renderMissingInputs(answer.missing_inputs);
  updateTranslateAllLabel();
}

function inputTypeFor(valueType) {
  if (valueType === "date") return "date";
  if (valueType === "int" || valueType === "float") return "number";
  return "text";
}

function renderMissingInputs(missingInputs) {
  const fields = el("missing-inputs-fields");
  fields.innerHTML = "";
  for (const input of missingInputs) {
    const wrap = document.createElement("div");

    const label = document.createElement("label");
    label.className = "missing-input-name";
    label.textContent = input.name;
    label.setAttribute("for", `missing-input-${input.name}`);

    const description = document.createElement("p");
    description.className = "missing-input-description";
    description.textContent = input.description;

    const field = document.createElement("input");
    field.type = inputTypeFor(input.value_type);
    field.id = `missing-input-${input.name}`;
    field.name = input.name;
    // Deliberately not `required`: several unrelated claims can each be
    // missing a different named input at once (e.g. sum_insured for the
    // room-rent panel, continuity_date for a waiting-period claim), and a
    // reader answering just one of them should be able to re-check
    // immediately rather than being blocked until every field is filled.
    if (extraProvidedInputs[input.name]) field.value = extraProvidedInputs[input.name];

    wrap.append(label, description, field);
    fields.appendChild(wrap);
  }
  el("inputs-panel").hidden = missingInputs.length === 0;
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

  body.appendChild(renderHindiToggle(claim));
  body.appendChild(renderChat(claim));

  head.addEventListener("click", () => {
    body.hidden = !body.hidden;
    head.setAttribute("aria-expanded", String(!body.hidden));
    disclosure.textContent = body.hidden ? "Why ▾" : "Why ▴";
  });

  li.append(head, body);
  return li;
}

/* Chat: a scoped secondary affordance for exactly three uses this project's
   own spec names — "why is this flagged", "show me the clause", "simpler
   language" — never a general-purpose "chat with your PDF" (out of scope,
   §2). Each button either reuses information already on the page (no new
   claim, no new risk of an ungrounded statement) or calls a narrow
   endpoint that rewords ALREADY-verified text under the same
   numeric-fidelity guarantee §9.4's translation uses. */
function renderChat(claim) {
  const wrap = document.createElement("div");
  const actions = document.createElement("div");
  actions.className = "chat-actions";
  const log = document.createElement("div");
  log.className = "chat-log";

  const chips = [
    makeChatChip("Why is this flagged?", () => {
      addChatBubble(log, "ask", "Why is this flagged?");
      addChatBubble(log, "answer", STATE_MEANING[claim.state] || "No explanation available.");
    }),
    makeChatChip("Show me the clause", () => {
      addChatBubble(log, "ask", "Show me the clause");
      if (claim.evidence.length > 0) {
        openEvidence(claim.evidence[0]);
      } else {
        addChatBubble(
          log,
          "answer",
          "There is nothing to show — no clause was found to check this against.",
          true
        );
      }
    }),
    makeChatChip("Explain more simply", async (chip) => {
      addChatBubble(log, "ask", "Explain more simply");
      chip.disabled = true;
      try {
        const res = await postJSON("/api/claims/simplify", { text: claim.text });
        addChatBubble(log, "answer", res.simplified);
      } catch (err) {
        addChatBubble(
          log,
          "answer",
          `Could not simplify this right now (${err.message || err}).`,
          true
        );
      } finally {
        chip.disabled = false;
      }
    }),
  ];
  if (claim.evidence.length === 0) chips[1].disabled = true;

  actions.append(...chips);
  wrap.append(actions, log);
  return wrap;
}

function makeChatChip(label, onClick) {
  const chip = document.createElement("button");
  chip.type = "button";
  chip.className = "chat-chip";
  chip.textContent = label;
  chip.addEventListener("click", () => onClick(chip));
  return chip;
}

function addChatBubble(log, kind, text, isError) {
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${kind}${isError ? " error" : ""}`;
  bubble.textContent = text;
  log.appendChild(bubble);
}

/* Hindi: §9.4 — "output must be translatable... Do not translate quoted
   clause text — show the original and the translation together." Every
   piece of GENERATED explanatory text (the overall summary, each claim's
   own statement, each follow-up question) is translatable this way — a
   quoted clause/evidence quote never is, since §9.4 forbids touching that.

   One shared implementation used by both the per-piece button next to
   each claim/question and the page-level "Translate everything" toggle
   (setupTranslateAll), so there is exactly one place that decides what
   "translated" looks like — never two divergent renderings of the same
   Hindi text.
*/
const HINDI_TOGGLE_LABEL = "Translate to Hindi · हिंदी में देखें";

/** Builds a small, self-contained translate control: optionally a button
 * (skip it with `showButton: false` where a page-level toggle already
 * covers this piece — the overall summary, sitting right next to the
 * global "Translate everything" button, doesn't need its own redundant
 * one too), plus the block its translation appears in once fetched.
 * Returns `{ element, translate }` — `element` is what to insert into the
 * page, `translate()` is the same action the button performs, exposed so
 * a page-level "translate everything" control can trigger every piece at
 * once without re-clicking each one individually. Idempotent: calling
 * `translate()` again (including via the button) just re-shows an
 * already-fetched translation instead of re-fetching it.
 */
function createTranslator(getSourceText, { showButton = true } = {}) {
  const wrap = document.createElement("div");
  let button = null;
  let block = null;

  async function translate() {
    if (block) {
      block.hidden = false;
      if (button) button.textContent = "Hide Hindi translation";
      return;
    }
    const text = getSourceText();
    if (!text) return;
    if (button) button.disabled = true;
    try {
      const res = await postJSON("/api/translate", { text });
      block = document.createElement("div");
      block.className = "hindi-block";
      const label = document.createElement("span");
      label.className = "hindi-label";
      label.textContent = "Hindi translation";
      const translated = document.createElement("p");
      translated.style.margin = "0";
      translated.textContent = res.translation;
      block.append(label, translated);
      wrap.appendChild(block);
      if (button) button.textContent = "Hide Hindi translation";
    } catch (err) {
      if (button) button.textContent = `Hindi unavailable (${err.message || err})`;
      throw err;
    } finally {
      if (button) button.disabled = false;
    }
  }

  if (showButton) {
    button = document.createElement("button");
    button.type = "button";
    button.className = "hindi-toggle";
    button.textContent = HINDI_TOGGLE_LABEL;
    button.addEventListener("click", () => {
      if (block && !block.hidden) {
        block.hidden = true;
        button.textContent = HINDI_TOGGLE_LABEL;
        return;
      }
      translate();
    });
    wrap.appendChild(button);
  }

  return { element: wrap, translate };
}

function renderHindiToggle(claim) {
  const translator = createTranslator(() => claim.text);
  translateAllTargets.push(translator.translate);
  return translator.element;
}

function updateTranslateAllLabel() {
  const button = el("translate-all");
  button.textContent =
    translateAllTargets.length > 0
      ? `Translate everything on this page to Hindi (${translateAllTargets.length} items)`
      : "Translate to Hindi";
  button.disabled = translateAllTargets.length === 0;
}

function setupTranslateAll() {
  const button = el("translate-all");
  updateTranslateAllLabel();
  button.addEventListener("click", async () => {
    button.disabled = true;
    button.textContent = "Translating…";
    // Settled rather than all() — one failed piece (e.g. a transient
    // Gemini error) should not stop the rest from showing their
    // translations; each already surfaces its own error inline.
    await Promise.allSettled(translateAllTargets.map((translate) => translate()));
    updateTranslateAllLabel();
  });
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
