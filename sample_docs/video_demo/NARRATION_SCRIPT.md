# 6-Minute Walkthrough — Narration Script

Read this aloud while recording (Cmd+Shift+5, screen + mic). Claude drives the browser/terminal
on each cue below, timestamped so you can see when to start talking. Every beat uses a real,
already-verified artifact in this repo, nothing staged for the camera.

Pre-flight (before you hit record):
1. Confirm the backend and dashboard are running (`http://localhost:8000/health`, `http://localhost:8501`).
2. Confirm `GOOGLE_API_KEY` has quota: `venv/bin/python -c "from app.services.llm_client import call_llm; print(call_llm('test','say OK'))"`.
3. Have a terminal and the dashboard both visible/switchable.

---

## 0:00–0:30 — Open

> "Most AI agent pilots don't fail on model quality. They fail because nobody set an acceptance
> threshold, nobody measured cost per task, nobody defined what happens when the agent is wrong,
> and nobody's name was on it. This is a proposal-response assistant for a professional-services
> bid team, and I'm going to show you the four places it's built to fail safely, not just the
> happy path."

*(Cue: Claude has the dashboard open, ready on the chat screen.)*

---

## 0:30–1:30 — Beat 1: the failure case, first

> "First, the failure case, because that's the one that actually costs money. I'm asking it about
> a consultant who doesn't exist in this firm's documents."

*(Cue: Claude types into the dashboard: "What is the day rate for Consultant James Okafor?")*

> "No such person appears anywhere in the corpus. Watch what it does."

*(Wait for response — expect a refusal, not a fabricated rate.)*

> "It refuses. It doesn't guess a plausible-sounding day rate. In a real proposal, a hallucinated
> commercial figure like that is far more expensive than a missed lookup — this is the check
> that's supposed to catch it before it ever reaches a client."

---

## 1:30–2:30 — Beat 2: the fix, a real cited answer

> "Now the question it actually can answer."

*(Cue: Claude types: "What is the day rate for a Senior Consultant?")*

> "£1,050 per day, excluding VAT, with a citation back to the source document. Every claim this
> system makes traces back to a specific document and page, not just this one."

*(Point out the citation marker and, if visible, the faithfulness score in the response.)*

> "That citation isn't decorative. There's a node in the graph that checks for it on every answer
> before it ever reaches the screen — if it's missing, the system doesn't let it through."

---

## 2:30–3:30 — Beat 3: what happens when the check fails

> "That citation check, and a faithfulness check next to it, are what catch an ungrounded answer.
> I can't reliably force the live model to fail on camera — that's the point, it's supposed to be
> rare — so here's the test suite proving the retry-then-escalate path actually works, not just
> described in a doc."

*(Cue: Claude switches to the terminal and runs:)*

```bash
pytest tests/test_rag_graph.py -k escalation -v
```

> "Three tests: an ungrounded answer gets retried and then escalated with a review banner if it's
> still bad after the retry cap, same for a missing citation, and a well-behaved answer on the
> first pass is never flagged. That's the difference between a low-confidence answer looking
> identical to a good one, and a bid director actually seeing the ones that need their sign-off."

---

## 3:30–4:30 — Beat 4: the data-boundary rejection

> "The fourth failure mode isn't about the answer, it's about what gets ingested in the first
> place. This firm's real demo once had a tuition-payment letter with real bank details reach the
> public corpus by accident, because nothing was checking. Here's the fix."

*(Cue: Claude uploads `sample_docs/video_demo/synthetic_bank_details_test.txt` — a synthetic
test fixture, a UK sort code and account number, no real data — via the dashboard's document
upload.)*

> "Rejected. HTTP 422, naming the exact pattern it found — a UK sort code — before the file ever
> touches the vector store or the disk. This is on by default, not something you have to
> remember to turn on per document."

---

## 4:30–5:15 — Close: the honest scorecard

> "All four of those are four of fifteen items on a production-readiness scorecard I built for
> this exact problem — the things that separate a demo from something that survives contact with
> a real engagement. As of today this repo is 9 demonstrated, 5 partial, and genuinely 1 open:
> per-user access control, a single shared API key for now, not a per-tenant permission model.
> I'm not going to pretend that one's solved."

*(Cue: show the scorecard — either the published artifact or `docs/FAILURE_MODES.md`.)*

---

## 5:15–6:00 — Sign-off

> "Everything in this video is reproducible from the public repo: the tests, the golden set, the
> scorecard, all of it. The link's in the description. If you're evaluating an agent pilot and
> want to know which of these fifteen things it's actually built, that's the review I offer."

*(End on the repo URL or the scorecard tally, whichever is on screen.)*

---

## Notes

- Total: ~6 minutes at a normal speaking pace. If you're running long, the scorecard close (4:30
  onward) is the easiest section to tighten — the four live beats are the part worth keeping
  full-length.
- If the live model gives an unexpected answer on Beat 1 or 2 (model variance is real, see the
  golden-set flakiness found 2026-10-05), pause, don't edit around it — either re-ask once or
  narrate what actually happened. A visibly real failure handled correctly in front of the camera
  is a point in your favour, not against it.
