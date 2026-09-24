# TypeSafe "System One" / Jev — implementation brief

Source: live docs at https://docs.typesafe.ai (all pages below fetched; every claim cited).
Nothing here is inferred beyond what the pages state; undocumented items are flagged.

## 1. HTTP request / response shape

**Endpoint** ([api.md](https://docs.typesafe.ai/api.md), [quickstart](https://docs.typesafe.ai/introduction/quickstart.md)):

```
POST https://api.typesafe.ai/v1/systemone
Authorization: Bearer <API_KEY>
Content-Type: application/json
```

**Request body** — three top-level fields:
- `state`: `string | object | array` — content to evaluate.
- `model`: `string`, required. Docs use `"jev-latest"`; SDK default is also `jev-latest`.
- `questions`: `map<string, Question>`. The key is your question id; it is **not sent to the model**.

`Question` fields: `type` (`"choice" | "score" | "noul"`), `instructions` (`string | object | array | null`), `criteria`.
- Choice `criteria`: `map<string, string | object | array | null>`, **max 255 options per Choice**.
- Score `criteria`: ordered `array` of levels, **at least 2, API accepts up to 10**.
- Noul `criteria`: optional object `{ "true": ..., "false": ... }`.

**Response**:
```json
{ "model": "jev-1.13.0",
  "answers": { "<your id>": { ... } },
  "usage": { "input_tokens": 296, "output_tokens": 20 } }
```
`model` echoes the **versioned id** that answered, not the alias.

**Every field carrying a probability or confidence** ([api.md](https://docs.typesafe.ai/api.md)):
- Noul answer: `type:"noul"`, `noul` (float 0–1, the probability of yes). **No `confidence` field.**
- Choice answer: `type:"choice"`, `choice` (highest-probability option), `probabilities` (`map<option, float>`, sums to 1), `confidence` (0–1).
- Score answer: `type:"score"`, `score` (probability-weighted mean of level indices, may land between levels), `legend` (`map<level#, description>`), `probabilities` (`map<level-as-string, float>`), `confidence` (0–1).

SDK note ([responses.md](https://docs.typesafe.ai/sdk/python/api/types/responses.md)): `ChoiceAnswer.probabilities` is `dict[str, float]`; `ScoreAnswer.probabilities` and `.legend` are keyed by **`int`**, not string.

**Errors** ([api.md](https://docs.typesafe.ai/api.md)): `401` bad key, `422` validation (body details offending field), `429` rate limit, `529` overloaded. Retry `429`/`529` with exponential backoff; SDKs do this by default and honour `retry-after`.

## 2. Python SDK

Package `typesafe-sdk` (`pip install typesafe-sdk` / `uv add typesafe-sdk`), **requires Python >= 3.10** ([quickstart](https://docs.typesafe.ai/introduction/quickstart.md), [sdk/python](https://docs.typesafe.ai/sdk/python.md)).

Env vars ([sync client](https://docs.typesafe.ai/sdk/python/api/clients/sync.md)): `TYPESAFE_API_KEY` (required), `TYPESAFE_DEFAULT_MODEL`, `TYPESAFE_BASE_URL`, `TYPESAFE_LOG_LEVEL`.

```python
TypeSafeClient(*, api_key: str | None = None, model: str | None = None,
               retry: RetryPolicy | None = None, timeout: float | httpx2.Timeout | None = None,
               headers: Mapping[str,str] | None = None, transport=None, http_client=None,
               base_url: str | None = None)
```
Explicit options beat env vars. Raises `TypeSafeError` if the key is missing/invalid.

```python
system_one(state: JSONContent,
           questions: Mapping[str, Question], *,
           model: str | None = None,
           retry: RetryPolicy | None = None,
           timeout: float | httpx2.Timeout | None = None,
           extra_headers: Mapping[str,str] | None = None,
           extra_body: Mapping[str, JSONValue | None] | None = None,
           response_model: type[ResponseT] | None = None) -> SystemOneResponse | ResponseT
```
`questions` accepts typed objects **or raw dicts**. `extra_body` is shallow-merged, last-write-wins. Answer access: `response.answers["id"]`, plus type-grouped `response.nouls` / `response.choices` / `response.scores`; `response.usage.input_tokens` / `.output_tokens`; `response.request_id` (from header `x-typesafe-request-id`); `response.raw_http_response`. `Answer` is a discriminated union on `type`. `client.models.list()` → `ListModelsResponse.models` (tuple of `ModelMetadata(name, description, release_date)`). There is also `AsyncTypeSafeClient` with the same surface.

**Minimal working snippet:**
```python
from typesafe_sdk import Choice, Noul, NoulCriteria, Score, TypeSafeClient

client = TypeSafeClient()  # TYPESAFE_API_KEY from env; model defaults to jev-latest

state = {
    "quote": {"last": 412.33, "prev_close": 410.10},
    "headline": "Chipmaker guides Q3 revenue below consensus; two brokers cut targets",
    "position": {"symbol": "NVDA", "qty": 1200, "unrealized_pct": -3.4},
}

resp = client.system_one(
    state=state,
    questions={
        "is_material_negative": Noul(
            instructions="Does `headline` convey materially negative, price-relevant news for the issuer?",
            criteria=NoulCriteria(true="Negative and price-relevant", false="Not price-relevant"),
        ),
        "action": Choice(
            instructions="Which action does the evidence support?",
            criteria={"hold": None, "trim": None, "exit": None, "add": None},
        ),
        "conviction": Score(
            instructions="How strong is the evidence for a directional move?",
            criteria=["none", "weak", "moderate", "strong"],
        ),
    },
)

print(resp.model)                                        # "jev-1.13.0"
print(resp.answers["is_material_negative"].noul)          # 0.0-1.0, no .confidence
a = resp.answers["action"];  print(a.choice, a.confidence, a.probabilities)
c = resp.answers["conviction"]; print(c.score, c.confidence, c.legend, c.probabilities)
```

## 3. Choice vs Score vs Noul

| Primitive | Answers | Returns |
|---|---|---|
| Choice | which of a fixed, unordered set | `choice`, `probabilities`, `confidence` |
| Score | position on ordered, described levels | `score`, `legend`, `probabilities`, `confidence` |
| Noul | is this true (yes/no) | `noul` (0–1) |

([primitives.md](https://docs.typesafe.ai/primitives.md))

Decision rule, verbatim intent: use **Choice** for one of a known set with no order; **Score** when the answer falls on a spectrum you can describe in steps; **Noul** for a clean yes/no where the probability itself is the signal. "If two types both seem to fit, prefer the one whose answer your code can act on directly." A Noul of 0.5 means yes and no are equally likely — **not** a medium degree. Use Score with written levels to measure degree; use Noul for a yes/no with a clear boundary. Add an `other`/`none of the above` Choice option when the list may not cover every input. Score `score` is the probability-weighted mean of level numbers; different distributions can yield the same score, so read `probabilities`/`confidence` alongside it.

## 4. Confidence vs probability

Probability is per-outcome (`probabilities`, or `noul` for a two-outcome question). `confidence` is a single 0–1 statistic derived from the **shape** of the distribution — concentrated = high, spread = low. Only Choice and Score answers carry `confidence`; "Noul answers don't carry one" ([confidence.md](https://docs.typesafe.ai/confidence.md)). You get the full `probabilities` because the docs explicitly say you are "never locked into our definition".

Concrete gating rule in code ([confidence.md](https://docs.typesafe.ai/confidence.md), [confidence-routing.md](https://docs.typesafe.ai/patterns/confidence-routing.md)):
```python
FLOOR = 0.60                      # catch genuinely-uncertain answers first
if a.confidence < FLOOR:                    escalate_to_human()
elif a.choice == "check_balance":           act()          # low stakes: 0.6 is enough
elif a.choice == "approve_transfer":
    act() if a.confidence > 0.85 else ask_user_to_confirm() # high stakes: 0.85 floor
```
For Noul, threshold the number directly, with a review band ([noul.md](https://docs.typesafe.ai/primitives/noul.md)): `NO, YES = 0.2, 0.8`; `NO < x < YES` → human; `x > YES` → act; else skip. Raise the yes-threshold when a false yes is expensive. Thresholds are domain-specific, must be tested on your data, and must not be carried across primitive types. In the guardrail cookbook the same cached assessment routed to `block` under one policy and `review` under another purely by changing `review_threshold`/`action_threshold` ([llm_guardrails](https://docs.typesafe.ai/cookbooks/llm_guardrails.md)).

## 5. Patterns for an automated trading / decision pipeline

- **Speculative fan-out** ([fan-out.md](https://docs.typesafe.ai/patterns/fan-out.md)): put every question the pipeline might need in one request — including branch-specific ones — then let code ignore the irrelevant answers. Measured: 13 questions batched in one call = **12.2x cheaper, 10.0x faster** than 13 calls, identical answers ([parallel_questions](https://docs.typesafe.ai/cookbooks/parallel_questions.md)).
- **Confidence-gated routing** ([confidence-routing.md](https://docs.typesafe.ai/patterns/confidence-routing.md)): one Choice for intent plus its `confidence` as a second axis; low-stakes action at a low threshold, irreversible action at a high one, everything below the floor to a human. Trade sketch: `intent` Choice of `{open_position, close_position, query, other}`; close/reduce requires confidence > 0.9, query at 0.6, below 0.6 → human.
- **Composite scoring** ([composite-scoring.md](https://docs.typesafe.ai/patterns/composite-scoring.md)): one Score per independent dimension, normalized to 0–1 by dividing by `len(criteria) - 1`, combined with weights held in code. Weights are editable without re-prompting, and the per-dimension scores stay visible for audit.
- **Intent routing** ([intent-routing.md](https://docs.typesafe.ai/patterns/intent-routing.md)): a Choice intent plus a complexity Score in one request; deterministic code handles one intent, specialist LLMs handle others, and `intent.confidence < 0.5` or `complexity.score > 1` (or its low confidence) routes to a human. Keeps expensive reasoning models off the common path.
- **Noul re-ranking** ([rerank_typesafe.md](https://docs.typesafe.ai/cookbooks/rerank_typesafe.md)): one Noul per query-candidate pair, score = the probability itself, then `sorted(shortlist, key=noul, reverse=True)`. Raised top-1 from 5%→18% and top-10 from 38%→62% on CLERC; 1,200 calls cost $0.0645.
- **Function-calling dispatcher** ([function_calling.md](https://docs.typesafe.ai/cookbooks/function_calling.md)): closed-set arguments (Python `Literal`) become one Choice each, booleans become flags, and each optional argument gets a companion Noul `"<arg>?"` asking whether the command mentions it at all — if not, the argument is omitted and the function default stands. The call's `confidence` is the **weakest** argument's probability, not the product (`call.confidence`, `call.weakest()`); one wrong argument spoils the call. 28 fillable arguments across ten trading functions exceeded the context budget in one request in that example — the spec was built from `Literal` type hints, not generated freehand.
- **Hazard screening** ([llm_guardrails.md](https://docs.typesafe.ai/cookbooks/llm_guardrails.md)): a battery of Nouls (one per hazard) plus a harm-severity Score, mapped through `HAZARD_ACTION` and `PRECEDENCE` to `pass` / `review` / `block` / `support`. Directly reusable for pre-trade or order-flow risk screening.
- **Confidence-tiered labels** ([classification_using_confidence.md](https://docs.typesafe.ai/cookbooks/classification_using_confidence.md)): one Choice over a taxonomy, and when `confidence` is below the cutoff roll the answer up to its parent node instead of dropping it. On 60 SEC filings a 0.9 cutoff split them in half: 90% correct above, 40% below, and 70% once the unsure half was reported one level up.

## 6. Operational limits

From [models.md](https://docs.typesafe.ai/models.md):
- Model: `jev-1.13.0`. Aliases: `jev-latest` → `jev-1.13.0` (SDK default), `jev-preview` → currently also `jev-1.13.0` (no preview build available).
- **Price: $42 per billion input tokens = $0.042 per million input tokens. Output tokens are free.** Charged on input only. Cookbooks use `PRICE = (0.042, 0.00)`.
- **Rate limits: 250,000 tokens/second and 1,200 requests/minute**; exceeding either returns `429`. The docs warn these limits "can change without notice".
- **Context: 64k tokens per request total; 32k tokens for `state` plus the single longest question.**
- Input is **text only** (string, JSON object, array). No image/audio/video. English is the primary training language; other languages, including CJK, are accepted but less accurate.
- Latency: "Most queries complete in about 100 ms" ([how-to-build](https://docs.typesafe.ai/concepts/how-to-build-with-system-one.md)). Measured in the batching cookbook: one call with 13 questions over a ~54k-character document took 0.27s; the 13 single-question calls summed to 2.71s.
- Batching: no documented maximum number of questions per request — the docs recommend putting **all** questions for a state in one call and note extra questions "barely change the response time". Per-question limits are Choice ≤ 255 options (a cookbook says Choice "works reliably up to roughly 240 options") and Score 2–10 levels.
- No fine-tuning or LoRA per customer; the same weights serve every account. Not trained on customer requests/responses; ZDR for enterprise.
- `GET /v1/models` lists the names your account may send.
- Not documented anywhere I fetched: streaming, async batch endpoints, per-account question caps, and any hard limit on `state` beyond the 32k/64k token budgets.

## 7. Anti-patterns and "do not do this"

From [model-jaggedness/jev-1.13.md](https://docs.typesafe.ai/model-jaggedness/jev-1.13.md) and the build/primitive pages:

1. **Do not ask the model anything code can compute exactly.** Jev "does not count reliably" (characters, occurrences, list items) and is "not a calculator" — do arithmetic, counts, and comparisons in code, and ask one question per candidate then tally.
2. **Do not use it for date/time ordering or arithmetic.** It "reads dates as text, not as ordered quantities". Extract date parts as Choices (with an explicit "not stated" option) and compare in code.
3. **Do not interpolate between Score levels to reconstruct a number.** "`jev-1.13`'s score levels are weak in numerical calibration." A Score can gate a threshold, not produce a magnitude.
4. **Do not hide several judgments inside one question.** "Analyze this message and determine the best course of action" is explicitly called out as a bad question; it is a signal to decompose.
5. **Do not stuff `state`.** Unrelated detail is a distractor and "Jev suffers from context rot"; accuracy falls as state grows with irrelevant content. Filter in code first.
6. **Do not assume adversarial robustness.** "State is data, and `jev-1.13` does not treat it as hostile by default" — injected instructions or self-arguing text can move the answer.
7. **Do not let `instructions` and `criteria` disagree.** An inverted Noul (`true` mapping to no) performs worse.
8. **Do not rely on structural invariance between questions.** Measured: the same question as a Noul gave 0.22 while the Choice gave yes 0.01 / no 0.99; a question and its negation returned 0.72 and 0.47 (sum 1.19). Don't carry a Noul threshold to a Choice; a Choice is relative, per-option Nouls are absolute.
9. **Do not use it to generate text.** "You can force it to by chaining choices, this will not work well and will be very slow."
10. **Do not use numeric-only Score levels.** Levels `["0","1","2"]` scored 0.55 at confidence 0.33 on a report that descriptive levels scored 0.0 at confidence 1.0. Levels must describe concrete situations and stand on their own.
11. **Do not put multiple dimensions in one Score level** ("punctual and smart and experienced") — confidence drops and the score means less.
12. **Do not rely on one question per call**, and do not assume a second request is needed: questions over the same state run in parallel, so a follow-up request is only justified when an earlier answer is needed to fetch evidence, build new state, or pick the next options.
13. **Do not treat `confidence` as correctness.** "Typed output guarantees the interface, not truth"; confidence summarizes distribution concentration, not workflow correctness or permission to act. Ignore uncertainty on unused branches, and test thresholds on your own data.
14. **Do not send one request per question in a loop from an agent** — the docs call out coding agents in particular for falling into this habit.
15. Do not rely on model weights for current facts; do not re-run inference to change a weight or a display filter; keep API credentials server-side. If you have tuned thresholds against a version, **pin the version id** rather than the moving alias.
