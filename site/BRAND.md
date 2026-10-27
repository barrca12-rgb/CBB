# Off The Glass: site style brief

For the NFL and NBA sites, so all three match the college basketball site
(https://barrca12-rgb.github.io/CBB/, styles in `cbb/report_html.py` of barrca12-rgb/CBB).

## Assets
Copy them from barrca12-rgb/CBB `site/assets/`. Use the same file names and put them in the Pages build under
`assets/`.

| File | Use |
|---|---|
| `otg-logo-512.png` | header logo (34 px, 7 px radius) and the footer follow link |
| `otg-banner.webp` | hero at the top of the record page |
| `otg-social.jpg` | link-preview image (1200x630) |
| `favicon-32.png`, `favicon-64.png`, `apple-touch-icon.png` | browser and home-screen icons |

## Colors (CSS variables)
- **Light:**
  - bg `#fbf6ea` (cream), surface `#ffffff`, sunken `#f7f0e1`;
  - line `#ebe1cd`, line-strong `#d9cbb0`;
  - text `#0a2c49` (navy), muted `#56627a`, faint `#8a93a3`;
  - accent (links) `#b84a08`, brand `#fd6c0f` (orange);
  - top bar `#0a2c49`, bar text `#fbf6ea`, bar muted `#b7c3d3`;
  - pos `#0f7b4b` / `#e6f4ed`, neg `#c2352b`, warn `#8a5a00` / `#fbf0d9`.
- **Dark** (`prefers-color-scheme: dark`):
  - bg `#08090b`, surface `#12151a`, sunken `#181c22`;
  - line `#242a33`, line-strong `#333b46`;
  - text `#f6eedd`, muted `#a8b0bc`, faint `#6f7886`;
  - accent `#ff8a3d`, brand `#fd6c0f`;
  - top bar `#000000`, bar text `#f6eedd`, bar muted `#9aa2ae`;
  - pos `#3ccf8e`, neg `#ff6b5e`.

## Type
- **Display:** Google Fonts "Graduate", for the wordmark (uppercase, 19 px) and page titles (h1, 26 px, weight
  400).
- **Text:** Inter 400-800, with tabular numbers (`font-feature-settings: "tnum"`).
- **Section titles:** Inter 800, 13 px, uppercase, letter-spacing .07em, with a 4x14 px orange bar before them.
- **Column headers and stat labels:** Inter 700, 11 px, uppercase, letter-spacing .05-.06em.

## Components
- **Top bar:**
  - sticky, bar color, 3 px orange bottom border, 58 px tall;
  - logo plus wordmark "Off The Glass";
  - sport tabs NFL / College Basketball / NBA in uppercase 13 px, active tab = bar text with a 3 px orange
    underline;
  - on phones the wordmark hides.
- **Cards/panels:** surface, 1 px line border, 10 px radius, shadow `0 1px 2px rgba(10,44,73,.06)`. The stat strip
  has a 3 px navy top border.
- **BET tags:** orange fill, white text. The best price stays green.
- **Team logos:** 14-20 px beside team names, from `https://a.espncdn.com/i/teamlogos/{league}/500/{espn_id}.png`
  (`500-dark` for dark mode), with `onerror` removing the image. Leagues: `ncaa`, `nfl`, `nba`.
- **Footer:** "Follow @OffTheGlassHQ on X for every play" (link https://x.com/OffTheGlassHQ), with the logo.

## Head tags
- `<title>`: "Off The Glass · {Sport} · {date}".
- Meta description, `theme-color` `#0a2c49`, the favicons above.
- Open Graph: site_name "Off The Glass", type, image = absolute URL of `otg-social.jpg`.
- `twitter:card` = summary_large_image, `twitter:site` = @OffTheGlassHQ.

## Public vs internal
- **Public:** the card, plays, odds board, power ratings, recent results, record with bets placed and the follow
  link.
- **Internal only (not on the site):** methodology and backtest claims, forward-test cohorts, verification links,
  model-change notes.
