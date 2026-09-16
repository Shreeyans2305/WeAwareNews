// Product catalog for Newsletters and Podcasts pages.
// These describe WeAware editions and shows, not real-world claims.

export const newsletters = [
  {
    id: 'the-crosscheck',
    name: 'The Crosscheck',
    cadence: 'Daily, 7 min',
    topic: 'Top stories',
    description:
      'Three stories that matter, each with consensus score, source stances, and one flagged claim to read twice.',
    sample: 'Frontier labs agree on evals, battery costs cross gas, Harbor treaty signed',
    accent: true,
  },
  {
    id: 'signal-field',
    name: 'Signal and Field',
    cadence: 'Weekly, 12 min',
    topic: 'AI and Climate',
    description:
      'Longer reads on systems changing fast. What agents corroborated, what stayed disputed, and which numbers to trust.',
    sample: 'Coding agents at 61 percent, coral ledger turns net positive, SAF mandate begins',
    accent: false,
  },
  {
    id: 'ledgerline-markets',
    name: 'Ledgerline Markets',
    cadence: 'Weekdays, 5 min',
    topic: 'Markets and World',
    description:
      'Rates, listings, and shipping pacts without the hype. Futures pricing labeled as pricing, guidance labeled as guidance.',
    sample: 'Rate hold repriced, IPO streak at three, rare earths up 22 percent',
    accent: false,
  },
]

export const episodes = [
  {
    id: 'ep-14-evals',
    show: 'WeAware Daily Brief',
    title: 'Shared safety evals, split timelines',
    duration: '18 min',
    date: 'Today',
    description:
      'Why three labs publish against one benchmark suite, and why their forecasts still span 22 months. With the flagged regulation claim unpacked.',
    topic: 'AI',
  },
  {
    id: 'ep-13-batteries',
    show: 'WeAware Daily Brief',
    title: 'Batteries beat gas peakers in three grids',
    duration: '15 min',
    date: 'Yesterday',
    description:
      'The crossover analysts expected in 2028 arrived early. What evening auctions show, and where gas still wins.',
    topic: 'Climate',
  },
  {
    id: 'ep-12-rates',
    show: 'The Disagreement',
    title: 'The bank said patience, markets heard cuts',
    duration: '24 min',
    date: 'This week',
    description:
      'One changed adjective moved futures to two cuts. Doves, hawks, and the headlines that said confirmed.',
    topic: 'Markets',
  },
  {
    id: 'ep-11-harbortreaty',
    show: 'The Disagreement',
    title: 'Twelve signatures, forty percent of tonnage outside',
    duration: '21 min',
    date: 'This week',
    description:
      'Nineteen days of talks, observer status for the largest flag states, and why 2028 is a hope, not a date.',
    topic: 'World',
  },
]
