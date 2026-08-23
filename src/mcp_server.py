"""Installed console entrypoint for the canonical stdio MCP server.

The implementation lives at the repository root so running the source file and
running the installed console script exercise the same server and tool set.
"""

import asyncio

from fantasy_football_multi_league import main as run_stdio_server


def main() -> None:
    """Run the async stdio server from a synchronous console entrypoint."""

    asyncio.run(run_stdio_server())


if __name__ == "__main__":
    main()
