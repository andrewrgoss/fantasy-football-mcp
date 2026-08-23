# FantasyPros Data

FantasyPros is an optional projection/ranking source. This repository supports
both the official API and user-downloaded CSV exports, but local CSVs are the
recommended path for a complete auction board.

## Requesting an API key

Request a key at [FantasyPros API Data](https://www.fantasypros.com/api-data/)
and review the current [terms of use](https://api.fantasypros.com/public/v2/terms-of-use).
Keys are for personal, non-commercial use under the published free terms. Do not
commit the key or use licensed player-image URLs without the appropriate rights.

Copy-ready response for the 600-character **How do you plan to use the API?**
field:

```text
I am building a private, single-user, non-commercial fantasy football MCP server for personal draft preparation and roster analysis. FantasyPros projections and consensus rankings will be combined locally with my own league settings, Yahoo market data, and historical position-level auction trends to estimate auction values and keeper surplus. The data will not be resold, redistributed, used for model training, or exposed as a competing public service. FantasyPros will be credited in any published derivative analysis.
```

Store the key only in `.env`:

```env
FANTASYPROS_API_KEY=your_key
FANTASYPROS_API_BASE_URL=https://api.fantasypros.com/public/v2/json
```

## Free API limitations

Testing with a free API key returned exactly 10 records per endpoint, even when
the response reported a much larger available population:

| Endpoint | Available | Returned |
| --- | ---: | ---: |
| QB projections | 83 | 10 |
| RB projections | 131 | 10 |
| WR projections | 191 | 10 |
| TE projections | 120 | 10 |
| Consensus rankings | 522 | 10 |

Each limited response included `limit: 10` and `public_api_limited: true`.
Calling the four position projection endpoints therefore produced only 40
projection records: four independent top-10 slices, not a complete player pool.

This was not ordinary pagination. The projection endpoint was tested with no
paging parameter and with `limit=200`, `offset=10`, `start=11`, and `page=2`.
Every request returned the same 10 rows and the same first player. The API
documentation did not expose pagination for projections, consensus rankings,
or player metadata. Filtering projections by known FantasyPros player IDs is
supported, but that does not provide a way to discover or retrieve the complete
pool from a limited key.

The separate player-metadata endpoint, which exposes fields such as
`rank_adp_ppr`, also returned only 10 records. In the observed response those
records were defensive teams, so none joined to the offensive auction pool and
the FantasyPros ADP column remained empty. The consensus endpoint populated
rank for only its 10 returned players. Missing projection, rank, and ADP values
were therefore absent from the API response rather than lost by the CSV writer
or parser.

One response-format quirk is also worth noting: projection responses identified
their scoring type as `STD` even when PPR was requested, while still including
`points_ppr`. The client deliberately selects `points_ppr` for full-PPR
analysis.

FantasyPros ranking CSV exports may contain `ECR VS. ADP`; that field is the
difference between ECR and ADP, not the player's actual ADP.

The client retains API support for users whose plan provides adequate coverage,
but a free limited response is not sufficient for a complete auction board.
The client must not fabricate missing fields: unavailable values remain blank,
and the auction blender renormalizes the sources present for each player.

## Recommended CSV workflow

Download the data you are permitted to use from your FantasyPros account. The
current loader supports:

- full-PPR FLX projections for RB/WR/TE;
- full-PPR QB projections; and
- overall draft rankings.

Configure their private paths:

```env
FANTASYPROS_PROJECTIONS_PATH=/private/path/FantasyPros_Projections_FLX.csv
FANTASYPROS_QB_PROJECTIONS_PATH=/private/path/FantasyPros_Projections_QB.csv
FANTASYPROS_RANKINGS_PATH=/private/path/FantasyPros_Draft_ALL_Rankings.csv
```

Or pass the equivalent `fantasypros_projection_path`,
`fantasypros_qb_projection_path`, and `fantasypros_rankings_path` arguments to
`ff_project_auction_values`.

FantasyPros projection files use repeated column names such as `YDS` and `TDS`.
The loader reads those rows positionally so rushing and receiving data are not
shifted. Local CSV paths take precedence over the API.

Do not commit downloaded FantasyPros files. The public files under
`data/examples/` use invented players and values to document the accepted
shape without redistributing FantasyPros data.

## Attribution and publication

Keep the workflow personal and non-commercial unless your agreement permits
more. Credit FantasyPros when publishing research or derivative analysis. Do
not publish raw downloaded datasets, private account files, or player images.
