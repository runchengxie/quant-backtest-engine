# Documentation site

The owner requested GitHub Pages, MkDocs, English/Chinese switching, dark mode and
the visual language of the existing Quant project documentation. Use MkDocs Material,
locked Python documentation dependencies, a warm neutral palette modeled on
quant-platform, and language-isolated navigation with localized theme controls like
quant-backtest-runtime. English is the default. Counterpart links preserve the page;
missing translations fall back to English. Theme preference uses Material storage.

Keep LICENSE, COPYING, Cargo.toml and Cargo.lock at project root. Move third-party
attribution to docs/third-party-notices.md and update references. Publish only merged
main commits through Actions artifacts, retaining GitHub environment protections.
PRs run strict build and rendered navigation/theme/local-link checks, never deploy.
No generated website output is committed. The site accurately describes current
engine capabilities while portfolio/market-rule migration remains active work.
