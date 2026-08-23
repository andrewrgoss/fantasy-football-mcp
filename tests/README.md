# Tests

The suite covers Yahoo request handling and parsing, MCP handlers, lineup and
bye-week behavior, Reddit privacy boundaries, and the offline auction workflow.

Run everything without writing pytest cache files:

```bash
.venv/bin/python -m pytest -p no:cacheprovider -q
```

Run the offline auction and Reddit privacy checks:

```bash
.venv/bin/python -m pytest -p no:cacheprovider -q \
  tests/unit/test_auction_prep.py \
  tests/unit/test_reddit_privacy.py
```

Run one area while developing:

```bash
.venv/bin/python -m pytest -p no:cacheprovider -q tests/unit/test_api_client.py
.venv/bin/python -m pytest -p no:cacheprovider -q tests/integration/
```

`tests/test_live_api.py` is an executable Yahoo diagnostic, not an ordinary
offline test. Run it directly only after Yahoo has provisioned the OAuth client
and local credentials are configured:

```bash
.venv/bin/python tests/test_live_api.py
```

Never add real league names, IDs, manager names, tokens, or proprietary exports
to fixtures. Use invented identities and minimal synthetic values.
