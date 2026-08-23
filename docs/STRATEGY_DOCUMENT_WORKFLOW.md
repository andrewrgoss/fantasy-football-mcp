# Strategy-Document Workflow

`ff_project_auction_values` produces a value board. A useful salary-cap draft
strategy document adds league constraints, keeper availability, roster
construction, budget pivots, and live-news judgment.

The final strategy document is an analyst artifact; the MCP does not currently
write it automatically. This separation is intentional because the document
often contains private league identities and judgment that should not be
committed.

## Required inputs

Keep these private:

- completed league profile;
- generated auction-value CSV;
- keeper rules and keeper-cost sheet;
- historical auction summary;
- known or projected keeper choices;
- current injury, transaction, and depth-chart notes; and
- manager-specific tendencies, if used.

The model board should be regenerated after material projection, market, keeper,
or team-context changes.

## Recommended sequence

### 1. Record hard league constraints

Include the salary cap, team count, scoring, starting lineup, flex rules, bench,
IR, keeper floor/escalation, keeper eligibility, and the platform's live maximum
bid rule.

These constraints determine replacement levels and how aggressively scarce
positions should be purchased.

### 2. State the data model

Document:

- projection-source weights;
- how missing sources are handled;
- market and historical calibration weights;
- whether historical prices are position-slot or player-name based;
- context adjustments and caps;
- unavailable integrations such as unapproved Reddit sentiment; and
- the as-of date for every time-sensitive source.

This makes the strategy auditable when a surprising value appears.

### 3. Evaluate the user's keeper options

For every eligible option, record:

- keeper cost;
- current model value;
- raw surplus;
- injury/role/team risk;
- positional scarcity; and
- fit with the intended auction build.

The largest mathematical surplus is not automatically the best roster choice.
A slightly smaller surplus at a scarce position or one of many required starting
slots can be more useful.

### 4. Project the opponent keeper board

For each opponent, compare eligible keeper cost with current value and include a
no-keeper option. Record alternatives that materially change the auction pool.

Then calculate:

- likely number and cost of keepers;
- dollars remaining in the room;
- roster spots remaining;
- which positional tiers are removed; and
- likely inflation pressure on the players who return to auction.

Use invented opponent labels in any public example. Never publish real manager
or team names.

### 5. Define positional tier breaks

Identify the positions where replacement becomes materially worse rather than
assuming a smooth ranking curve. Tie each tier to a target price and hard ceiling.

The strategy should explicitly say what to do if a likely keeper removes a
member of a scarce tier.

### 6. Build a legal budget shell

Create one primary budget and at least two pivots. Every shell must:

- include the keeper cost;
- fill every required auction roster spot;
- reserve the platform minimum for every open spot; and
- sum exactly to the salary cap.

The live maximum bid is generally:

```text
maximum bid = dollars remaining - (open roster spots - 1)
```

That formula is a hard ceiling, not a recommendation to spend it.

### 7. Add execution rules

Document early-, middle-, and late-auction behavior, nomination tactics, budget
tracking, position-closing risks, and the conditions that trigger each pivot.

Finish with a short checklist that can be used during the live draft.

## Suggested prompt

After generating the private board, a local assistant can be asked:

```text
Using my private league profile, auction-value CSV, keeper sheet, historical position-slot summary, and current player-news notes, create a salary-cap draft strategy. Include league constraints, source weights, keeper recommendation, projected opponent keepers including no-keeper alternatives, expected auction-pool inflation, positional tier breaks, a budget that preserves $1 for every open roster slot, pivot budgets, nomination tactics, and a final checklist. Keep all outputs in my private directory and do not copy league or manager identities into the repository.
```

## Public example

[`auction_draft_strategy.example.md`](../examples/auction_draft_strategy.example.md)
shows the recommended structure with invented league, opponent, player, and
price data. It is not derived from or usable for a real private league.

## Sanitization checklist

Before publishing an example:

- replace the league name and ID;
- replace manager/team names;
- replace keeper players and prices if they came from a private sheet;
- remove private paths and filenames;
- replace historical results with invented rows;
- do not reproduce proprietary projection datasets;
- preserve only general settings/methodology; and
- verify the result with `git grep` before committing.
