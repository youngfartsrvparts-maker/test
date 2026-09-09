# Sleeper Fantasy Cloud Bridge

Cloud bridge for the 2026 10-team Sleeper league used by ChatGPTJagger.

League ID: `1388315713940262912`
Sleeper user: `ChatGPTJagger`
Sleeper user ID: `1394868996146204672`

A GitHub Actions job refreshes the league snapshot from Sleeper's public read-only API and commits normalized JSON into `data/`.

Key outputs after the first successful sync:
- `data/status.json`
- `data/league.json`
- `data/teams.json`
- `data/my_team.json`
- `data/free_agents.json`
- `data/matchups.json`
- `data/transactions.json`
- `data/trending.json`
- `data/drafts.json`

The Sleeper player directory is cached and refreshed at most once per UTC day, in line with Sleeper's guidance for the large players endpoint.
