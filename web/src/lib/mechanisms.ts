// Navigation groups do not change the source-bound lesson identities.
export const mechanisms = [
  { id: 'portfolio', scene: 'lots', reference: 'concepts/impact-optimization-scenarios' },
  { id: 'feedback', scene: 'book', reference: 'concepts/impact-planning' },
  { id: 'cost', scene: 'cost', reference: 'backtest/cost-evidence' },
  { id: 'impact', scene: 'impact', reference: 'concepts/impact-optimization-scenarios' },
  { id: 'paths', scene: 'paths', reference: 'product/scenarios' },
  { id: 'microstructure', scene: 'book', reference: 'development/microstructure-rust' },
] as const;
export const frameworkReferences = [
  { id: 'nautilus', href: 'https://nautilustrader.io/docs/latest/concepts/backtesting/' },
  { id: 'hft', href: 'https://hftbacktest.readthedocs.io/en/latest/' },
  { id: 'backtrader', href: 'https://www.backtrader.com/docu/' },
] as const;
