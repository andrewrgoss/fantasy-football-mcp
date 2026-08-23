# Example Salary-Cap Draft Strategy

> This is a sanitized example. The league, opponents, players, keeper costs,
> projections, history, and prices are invented. It contains no private league
> data and is not a usable 2026 player ranking.

**Prepared:** Example date

**League:** Example Salary-Cap League

**Team:** Example Team

**Budget:** $200
**Teams:** 10

## League constraints

- One keeper per team with a $10 minimum keeper cost.
- A player cannot be kept in consecutive seasons.
- Full PPR scoring.
- Starters: QB, 2 RB, 2 WR, TE, 2 FLEX, DEF.
- Six bench spots; no kicker.
- The platform requires $1 for every unfilled auction roster spot.
- Waivers use a free-agent budget, making a cheap, replaceable bench viable.

The lineup creates six weekly RB/WR/TE starting slots. Full PPR raises the value
of routes, targets, receptions, and backs who remain involved when their team is
trailing.

## Data and valuation model

Example projection weights:

| Projection source | Weight |
| --- | ---: |
| Source A | 40% |
| Source B | 30% |
| Source C | 30% |

Missing sources are omitted and the remaining weights are renormalized for that
player. Current market prices and historical auction prices are separate
calibration layers.

Historical prices are position-slot based. The current RB12 is compared with
the example league's historical RB12 salary, not the old salaries paid for that
same player.

Context signals are small:

- strength of schedule: maximum 2.5%;
- offensive-line rank: maximum 2.5%; and
- expected team strength: maximum 2.5%.

Line and team environment apply to QB, RB, WR, and TE. Receiving backs are
partially protected from a poor-team penalty. These inputs break close calls;
they do not override elite talent, volume, injuries, or a current depth chart.

No social-media adjustment is included because an approved signal is not
available. The board omits the corresponding fields instead of inventing a
neutral value.

## Historical auction tendencies

Invented historical spending shares:

| Position | Average share |
| --- | ---: |
| RB | 43% |
| WR | 40% |
| TE | 9% |
| QB | 7% |
| DEF | 1% |

The room historically spends aggressively on the first 15 running backs and
then shifts to wide receiver. The strategy should secure an RB1 before the
scarce tier closes but should not chase an early-down back solely because the
room is spending.

## Keeper recommendation

### Preferred keeper: Example Receiver A at $18

| Option | Cost | Model value | Surplus | Decision |
| --- | ---: | ---: | ---: | --- |
| Example Receiver A | $18 | $33 | +$15 | Keep if healthy |
| Example Receiving Back A | $10 | $22 | +$12 | Strong alternative |
| Example Tight End A | $24 | $29 | +$5 | Pass; little flexibility |
| Example Quarterback A | $10 | $13 | +$3 | Pass; position is deep |

Example Receiver A supplies a stable weekly starter and lets the auction focus
on two running backs and the premium tight-end tier. The slightly larger
receiver surplus also fits the league's two required WR slots.

The final choice must be health-checked before the deadline. A stale projection
does not outweigh a new injury or role change.

## Projected opponent keepers

Opponent labels and all values are invented.

| Opponent | Likely choice | Cost | Value | Surplus | Alternative |
| --- | --- | ---: | ---: | ---: | --- |
| Opponent 1 | Example RB B | $14 | $32 | +$18 | None |
| Opponent 2 | Example WR B | $10 | $25 | +$15 | Example QB B at $10 |
| Opponent 3 | Example TE B | $10 | $23 | +$13 | None |
| Opponent 4 | Example RB C | $22 | $31 | +$9 | No keeper |
| Opponent 5 | Example WR C | $17 | $29 | +$12 | None |
| Opponent 6 | No keeper | $0 | — | $0 | Example WR D at $24 |
| Opponent 7 | Example RB D | $10 | $24 | +$14 | None |
| Opponent 8 | Example WR E | $13 | $27 | +$14 | None |
| Opponent 9 | Example QB C | $10 | $16 | +$6 | No keeper |

Eight to nine opponent keepers would remove several mid-priced RB/WR values and
one premium TE. Recalculate the auction pool after declarations; do not assume
the projection is final.

## Positional plan

### Tight end

The model shows a three-player premium tier followed by a meaningful projection
drop. Buy one of the premium three only below the hard ceiling. If one is kept,
the remaining two will likely inflate; prepare a mid-tier pivot before the last
premium player is nominated.

### Quarterback

The first eight quarterbacks form a usable tier. Target $5–10 and avoid paying a
scarcity premium after the tier has already closed. If the room overpays, take a
late option and move the savings to RB.

### Running back

Prioritize receiving work, third-down participation, and stable goal-line
access. A strong line and offense are small positives, but a talented receiving
back can remain valuable on a losing team. Avoid paying a top-15 price for a
touchdown-dependent runner with little passing-game work.

Preferred build: one hero RB and one strong RB2. If hero prices become
irrational, pivot to two receiving-oriented backs from the next tier.

### Wide receiver

The keeper fills one starting WR slot. Buy one high-volume WR and use the flex
spots for the best RB/WR values rather than forcing a second expensive receiver.

### Defense and bench

- Defense: $1.
- Bench: six $1 players in the primary build.
- Favor contingent-value RBs, young route earners, and ambiguous depth charts.
- Use waivers rather than paying for low-upside bench certainty.

## Primary $200 budget

| Slot | Budget |
| --- | ---: |
| Example Receiver A keeper | $18 |
| Hero RB | $55 |
| RB2 | $31 |
| Additional starting WR | $46 |
| Premium TE | $22 |
| QB | $8 |
| FLEX 1 | $8 |
| FLEX 2 | $5 |
| DEF | $1 |
| Six bench players | $6 |
| **Total** | **$200** |

This shell preserves $1 for every roster spot. The anchor prices are targets,
not permission to exceed a hard ceiling.

## Pivots

### Premium TE becomes too expensive

Move $10–12 from TE to RB2 or FLEX 1 and select a mid-tier TE. Do not wait for
the final premium TE and then pay above the planned ceiling.

### Hero RB tier inflates

Replace the $55 hero allocation with two backs in the $30–38 range. Reduce FLEX
spending if necessary, but preserve receiving volume.

### Quarterbacks are inexpensive

An elite QB is acceptable only if the price remains below its value and does not
prevent the RB2 purchase. The default plan still prefers depth at QB.

## Auction execution

### Early

- Nominate expensive players outside the preferred build.
- Observe whether RB, WR, or TE is inflating before changing ceilings.
- Buy a preferred anchor when the price is fair; early does not automatically
  mean overpriced.

### Middle

- Complete RB2 before the reliable tier closes.
- Track every opponent's dollars and open positions.
- Do not bid against a team that can no longer use the nominated position as if
  it were still a threat.

### Late

- Preserve the $1-per-slot rule.
- Buy the quarterback value rather than a name.
- Fill defense and bench at the minimum.

Live maximum bid:

```text
maximum bid = dollars remaining - (open roster spots - 1)
```

## Draft-day checklist

- [ ] Keeper eligibility and health confirmed.
- [ ] Declared opponent keepers entered into the board.
- [ ] Remaining room dollars and roster spots recalculated.
- [ ] Each target has a target price, hard ceiling, and fallback tier.
- [ ] Premium TE availability confirmed.
- [ ] Hero RB and RB2 plans remain legal under the $1-per-slot rule.
- [ ] Current injuries, transactions, depth charts, line changes, and team news
      reviewed.
- [ ] Defense and bench minimums protected.

## Bottom line

Keep the discounted receiver, purchase one high-volume RB1 and a strong RB2,
take a premium TE only within the ceiling, and spend down at QB, defense, and
the bench. Treat team context as a small input and current role/news as a hard
override.
