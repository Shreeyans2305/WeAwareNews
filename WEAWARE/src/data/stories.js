// Dummy frontend-only dataset. All outlets, people and events are fictional.

export const TOPICS = ['AI', 'Climate', 'Markets', 'World', 'Good News']

export const stories = [
  {
    id: 'ai-frontier-evals',
    topic: 'AI',
    title: 'Frontier labs agree on shared safety evals, differ on timelines',
    summary:
      'Three leading AI labs will publish results against a common benchmark suite — but their forecasts for next-generation systems span nearly two years.',
    body: [
      'Three frontier AI laboratories announced they will evaluate their next models against a shared public benchmark suite covering deception, power-seeking behavior, and autonomous replication. The commitment, published simultaneously on Monday, is the first time rival labs have agreed on identical test conditions before release.',
      'Where the labs diverge is on what the results will mean. Meridian’s research note argues the suite measures "necessary but not sufficient" conditions for safe deployment, while Northbeam researchers claim passing scores should gate any wide release. Ledgerline declined to endorse either interpretation, calling the benchmarks "a floor, not a verdict."',
      'Independent auditors welcomed the move but noted the suite is voluntary, with no mechanism to verify that published scores match internal runs. WeAware agents flagged two outlets that reported the agreement as "binding regulation" — it is not; no regulator is party to the announcement.',
    ],
    consensus: 78,
    sources: [
      { outlet: 'Meridian Wire', stance: 'agree', note: 'Reports the joint commitment and quotes all three labs.' },
      { outlet: 'Northbeam Post', stance: 'context', note: 'Adds that the benchmarks are voluntary with no verification mechanism.' },
      { outlet: 'Ledgerline', stance: 'context', note: 'Notes timelines differ by up to 22 months between labs.' },
      { outlet: 'The Daily Signal', stance: 'dispute', note: 'Describes the deal as "binding regulation" — no regulator is involved.' },
    ],
    flaggedClaims: [
      {
        claim: '"Binding regulation" governs the new benchmarks.',
        reason: 'No regulator is party to the announcement; participation is voluntary.',
      },
    ],
    image: '/news/ai-1.jpg',
    publishedAt: '2h ago',
    readMins: 4,
  },
  {
    id: 'ai-agent-uptime',
    topic: 'AI',
    title: 'Autonomous coding agents cross 60% task completion in industry trial',
    summary:
      'A 40-company trial of autonomous coding agents reports record completion rates — though reviewers note the tasks were cherry-picked for agent-friendly work.',
    body: [
      'A consortium of forty software firms released results from a six-week trial of autonomous coding agents, reporting that agents completed 61% of assigned tickets without human intervention, up from 38% in a comparable trial last year.',
      'The headline figure comes with caveats the consortium disclosed itself: tasks were pre-screened for clear acceptance criteria, and agents worked in sandboxed repositories with full test suites. Performance on legacy codebases with sparse tests was roughly half the headline rate.',
      'Labor economists quoted across coverage split on implications. Some argue the gains compress junior-level busywork; others warn the trial says little about open-ended engineering. Agents flagged one viral post claiming "61% of developers replaced" — the trial measured tickets, not jobs.',
    ],
    consensus: 71,
    sources: [
      { outlet: 'Ledgerline', stance: 'agree', note: 'Covers the 61% figure with the consortium’s own caveats.' },
      { outlet: 'Signal & Field', stance: 'context', note: 'Emphasizes tasks were pre-screened; legacy-code performance far lower.' },
      { outlet: 'Northbeam Post', stance: 'context', note: 'Quotes economists split on labor implications.' },
      { outlet: 'Viral repost (social)', stance: 'dispute', note: 'Claims "61% of developers replaced" — the trial measured tickets, not jobs.' },
    ],
    flaggedClaims: [
      {
        claim: 'Agents replaced 61% of developers in the trial.',
        reason: 'The metric is tickets completed without intervention, not headcount. No layoffs were studied.',
      },
    ],
    image: '/news/ai-2.jpg',
    publishedAt: '5h ago',
    readMins: 5,
  },
  {
    id: 'ai-chip-exports',
    topic: 'AI',
    title: 'New chip export rules split analysts on enforcement odds',
    summary:
      'Fresh export controls target high-bandwidth AI accelerators, but smuggling routes and stockpiled inventory could blunt the impact for a year or more.',
    body: [
      'New export controls restrict sales of AI accelerators above a defined interconnect-bandwidth threshold, closing a loophole that let last-generation flagship chips ship under earlier performance-per-watt limits.',
      'Enforcement is the open question. Two think tanks estimate existing stockpiles cover 9–14 months of demand in restricted markets, and customs data reviewed by Meridian shows a 300% rise in re-exports through third countries since the first control round.',
      'Chipmakers publicly project "minimal revenue impact," a claim agents flagged as low-confidence: all three firms declined to disclose what share of sales flows through the newly restricted channels.',
    ],
    consensus: 64,
    sources: [
      { outlet: 'Meridian Wire', stance: 'agree', note: 'Details the threshold change and cites customs re-export data.' },
      { outlet: 'Harborlight Review', stance: 'context', note: 'Estimates 9–14 months of stockpiled cover in restricted markets.' },
      { outlet: 'Ledgerline', stance: 'context', note: 'Notes chipmakers claim minimal impact without disclosing channel mix.' },
      { outlet: 'Chipmaker statements', stance: 'dispute', note: '"Minimal revenue impact" is unverifiable from public filings.' },
    ],
    flaggedClaims: [
      {
        claim: 'Chipmakers face "minimal revenue impact."',
        reason: 'Low-confidence: firms did not disclose sales through restricted channels.',
      },
    ],
    image: '/news/ai-3.jpg',
    publishedAt: '8h ago',
    readMins: 4,
  },
  {
    id: 'climate-coral-ledger',
    topic: 'Climate',
    title: 'Coral restoration ledger shows first net-positive reef sector',
    summary:
      'A monitored Pacific reef sector now hosts more live coral than before bleaching — the first documented net-positive recovery at sector scale.',
    body: [
      'Marine biologists report the first net-positive coral recovery at sector scale: a 40-hectare monitored zone in the western Pacific now holds 12% more live coral cover than its pre-bleaching baseline, after five years of outplanting heat-tolerant fragments.',
      'The team stresses the result is local, not a trend. Globally, reef cover continues to decline, and the restored sector survived only because two forecast marine heatwaves veered away. "We got lucky with the weather and good with the science," the lead author said.',
      'Coverage is broadly consistent, though one outlet framed the finding as "reefs recovering worldwide" — agents flagged the extrapolation as unsupported by the paper, which explicitly limits claims to the study sector.',
    ],
    consensus: 82,
    sources: [
      { outlet: 'Harborlight Review', stance: 'agree', note: 'Reports the 12% net-positive figure with the sector-scale caveat.' },
      { outlet: 'Meridian Wire', stance: 'agree', note: 'Quotes the lead author on heatwaves veering away.' },
      { outlet: 'Northbeam Post', stance: 'context', note: 'Adds global reef cover is still declining.' },
      { outlet: 'Coastal Morning', stance: 'dispute', note: 'Headline implies worldwide reef recovery — the paper claims one sector.' },
    ],
    flaggedClaims: [
      {
        claim: 'Coral reefs are "recovering worldwide."',
        reason: 'The study documents one 40-hectare sector; global cover is still declining.',
      },
    ],
    image: '/news/climate-1.jpg',
    publishedAt: '3h ago',
    readMins: 4,
  },
  {
    id: 'climate-grid-storage',
    topic: 'Climate',
    title: 'Grid-scale battery costs fall below gas peaker plants in three markets',
    summary:
      'Four-hour battery storage now undercuts gas peakers on levelized cost in three major grids — a crossover analysts expected no earlier than 2028.',
    body: [
      'Levelized-cost analysis shows four-hour battery storage beating new gas peaker plants in three major electricity markets, driven by a 40% year-on-year fall in cell prices and record deployment volumes.',
      'Grid operators confirm batteries now win most evening-peak auctions in those markets. Gas retains advantages for multi-day shortfalls, and analysts caution the crossover depends on continued low lithium prices, which have swung 70% in past cycles.',
      'Industry coverage largely agrees on the numbers; disagreement centers on speed of replication. Ledgerline projects five more markets crossing over within 18 months, while Harborlight argues interconnection queues will bottleneck all but two.',
    ],
    consensus: 88,
    sources: [
      { outlet: 'Ledgerline', stance: 'agree', note: 'Reports the crossover with auction data from all three markets.' },
      { outlet: 'Harborlight Review', stance: 'context', note: 'Confirms wins at evening peak; gas still covers multi-day gaps.' },
      { outlet: 'Signal & Field', stance: 'context', note: 'Flags lithium price volatility as a risk to the trend.' },
    ],
    flaggedClaims: [],
    image: '/news/climate-2.jpg',
    publishedAt: '6h ago',
    readMins: 5,
  },
  {
    id: 'climate-aviation-fuel',
    topic: 'Climate',
    title: 'Green aviation fuel mandate begins — airlines warn of ticket impact',
    summary:
      'A 2% sustainable-fuel blending mandate takes effect for major carriers; airlines project single-digit fare rises while producers say supply will lag.',
    body: [
      'A 2% sustainable aviation fuel blending mandate took effect this week for carriers above a passenger threshold, the first enforceable quota of its kind. Regulators estimate compliance adds roughly 1–2% to average fares.',
      'Airlines project higher pass-through costs of 3–5%, citing forward SAF prices nearly triple those of conventional jet fuel. Fuel producers counter that contracted volumes will pull prices down within two years — a forecast agents marked low-confidence given only one commercial-scale plant is currently online.',
      'Environmental groups split: some call the mandate a floor worth celebrating, others argue 2% is negligible against traffic growth of 4% annually.',
    ],
    consensus: 66,
    sources: [
      { outlet: 'Northbeam Post', stance: 'agree', note: 'Covers the mandate terms and the 1–2% regulator fare estimate.' },
      { outlet: 'Meridian Wire', stance: 'context', note: 'Airlines project 3–5% fare impact on forward fuel prices.' },
      { outlet: 'Ledgerline', stance: 'context', note: 'Only one commercial-scale SAF plant is currently online.' },
      { outlet: 'Producer consortium', stance: 'dispute', note: '"Prices fall within two years" rests on unbuilt capacity.' },
    ],
    flaggedClaims: [
      {
        claim: 'SAF prices "will fall within two years."',
        reason: 'Low-confidence: depends on plants not yet built or financed.',
      },
    ],
    image: '/news/climate-3.jpg',
    publishedAt: '11h ago',
    readMins: 4,
  },
  {
    id: 'markets-rate-hold',
    topic: 'Markets',
    title: 'Central bank holds rates, signals patience — markets hear a cut',
    summary:
      'Policymakers voted to hold and stressed data-dependence; futures traders promptly priced two cuts this year anyway.',
    body: [
      'The central bank held its policy rate steady for the third consecutive meeting, with the statement emphasizing "patience" and "data-dependence" amid sticky services inflation.',
      'Markets heard something dovish regardless: futures now price two quarter-point cuts this year, up from one before the decision, seizing on a single changed adjective in the statement and the chair’s remark that policy is "well positioned."',
      'Economists are split on who is misreading whom. Doves argue the bank is quietly making room as labor softens; hawks note the chair explicitly refused to "pre-commit to any path." Agents flagged three headlines declaring cuts "confirmed" — nothing was confirmed.',
    ],
    consensus: 58,
    sources: [
      { outlet: 'Ledgerline', stance: 'agree', note: 'Reports the hold and the "patience" language verbatim.' },
      { outlet: 'Meridian Wire', stance: 'context', note: 'Futures repriced to two cuts on one changed adjective.' },
      { outlet: 'Harborlight Review', stance: 'context', note: 'Labor softening gives doves ammunition; inflation gives hawks theirs.' },
      { outlet: 'Market blogs', stance: 'dispute', note: 'Multiple posts declare cuts "confirmed" — the chair refused to pre-commit.' },
    ],
    flaggedClaims: [
      {
        claim: 'Rate cuts are "confirmed" for this year.',
        reason: 'The statement stresses patience; futures pricing is speculation, not guidance.',
      },
    ],
    image: '/news/markets-1.jpg',
    publishedAt: '1h ago',
    readMins: 3,
  },
  {
    id: 'markets-rare-earths',
    topic: 'Markets',
    title: 'Rare-earth prices spike as refiners throttle output',
    summary:
      'Refined neodymium prices jumped 22% in a month as dominant refiners curb output — automakers say EV motor costs face pressure by Q3.',
    body: [
      'Prices for refined neodymium, critical for EV traction motors, rose 22% in four weeks after major refiners announced coordinated output curbs, citing environmental compliance costs.',
      'Automakers with long-term contracts are insulated through mid-year, but spot buyers — mostly smaller suppliers — face immediate margin pressure. Two European motor plants have already trimmed shifts.',
      'Analysts disagree on duration. Bulls see a multi-quarter squeeze accelerating non-Chinese refining projects; bears note identical spikes in 2021 and 2023 unwound within months once curbs eased. WeAware consensus sits low until inventory data clarifies.',
    ],
    consensus: 61,
    sources: [
      { outlet: 'Ledgerline', stance: 'agree', note: 'Tracks the 22% move with refiner announcements.' },
      { outlet: 'Signal & Field', stance: 'context', note: 'Contracted automakers insulated; spot buyers hit now.' },
      { outlet: 'Northbeam Post', stance: 'context', note: 'Two European motor plants trimmed shifts.' },
      { outlet: 'Commodity desks', stance: 'dispute', note: 'Split between multi-quarter squeeze and a repeat of 2021/2023 unwinds.' },
    ],
    flaggedClaims: [
      {
        claim: 'EV prices must rise immediately.',
        reason: 'Contracted supply insulates major automakers through mid-year; impact is concentrated in spot buyers.',
      },
    ],
    image: '/news/markets-2.jpg',
    publishedAt: '4h ago',
    readMins: 4,
  },
  {
    id: 'markets-ipo-window',
    topic: 'Markets',
    title: 'IPO window creaks open as three listings pop on debut',
    summary:
      'Three consecutive IPOs closed up 20%+ on debut, the strongest streak in two years — bankers urge caution against calling a reopening.',
    body: [
      'Three listings in ten days each closed their debut session up more than 20%, the strongest IPO streak in two years, rekindling debate over whether the long-frozen new-issue window is reopening.',
      'Notably, all three were profitable, mid-sized software firms — a narrow profile. Bankers caution the sample proves appetite for "boring, profitable growth," not a broad reopening; the backlog of large venture-backed listings remains untouched.',
      'Coverage agrees on facts and mostly on interpretation — a rare high-consensus story. The lone outlier, a newsletter claiming "the IPO boom is back," was flagged for extrapolating three data points into a cycle call.',
    ],
    consensus: 91,
    sources: [
      { outlet: 'Ledgerline', stance: 'agree', note: 'Reports all three debuts with first-day closes.' },
      { outlet: 'Meridian Wire', stance: 'agree', note: 'Notes all three are profitable mid-sized software firms.' },
      { outlet: 'Harborlight Review', stance: 'context', note: 'Large venture-backed backlog still untouched.' },
      { outlet: 'Deal newsletter', stance: 'dispute', note: '"IPO boom is back" extrapolates three listings into a cycle.' },
    ],
    flaggedClaims: [
      {
        claim: 'The "IPO boom is back."',
        reason: 'Three profitable mid-cap debuts do not constitute a broad reopening.',
      },
    ],
    image: '/news/markets-3.jpg',
    publishedAt: '9h ago',
    readMins: 3,
  },
  {
    id: 'world-harbor-treaty',
    topic: 'World',
    title: 'Harbor treaty signed after marathon talks, ratification unclear',
    summary:
      'Twelve nations signed a shipping-emissions pact after 19 days of talks — but the two largest flag states only observer-signed, clouding enforcement.',
    body: [
      'Twelve nations signed the Harbor Treaty on shipping emissions after nineteen days of continuous negotiation, committing signatories to port-fee differentials favoring low-emission vessels from 2028.',
      'The signatures that matter most are missing: the two largest flag states signed only as observers, meaning roughly 40% of global tonnage sits outside the pact’s enforcement mechanism. Negotiators call observer status "a foot in the door"; critics call it a veto by absence.',
      'Ratification timelines differ wildly — three parliaments could ratify within months, while others face elections that may reshuffle negotiating teams. Agents flagged claims the treaty "takes effect in 2028" as premature: it takes effect only after ratification thresholds neither text nor signatories have yet met in full.',
    ],
    consensus: 69,
    sources: [
      { outlet: 'Meridian Wire', stance: 'agree', note: 'Reports the signing and the 19-day negotiation.' },
      { outlet: 'Northbeam Post', stance: 'context', note: 'Two largest flag states are observers only; ~40% of tonnage outside.' },
      { outlet: 'Signal & Field', stance: 'context', note: 'Ratification timelines range from months to post-election unknowns.' },
      { outlet: 'Wire headlines', stance: 'dispute', note: '"Takes effect in 2028" is premature — thresholds unmet.' },
    ],
    flaggedClaims: [
      {
        claim: 'The treaty "takes effect in 2028."',
        reason: 'Effectiveness requires ratification thresholds that have not been met.',
      },
    ],
    image: '/news/world-1.jpg',
    publishedAt: '7h ago',
    readMins: 5,
  },
  {
    id: 'world-quake-response',
    topic: 'World',
    title: 'Relief corridors open after highlands quake; aid groups urge coordination',
    summary:
      'Two humanitarian corridors opened 72 hours after the highlands earthquake as the death toll passed 800 — responders warn uncoordinated convoys are clogging the single mountain road.',
    body: [
      'Authorities opened two humanitarian corridors 72 hours after a magnitude 6.8 earthquake struck the remote highlands, where the confirmed death toll has passed 800 and an estimated 40,000 are displaced.',
      'Relief groups welcome the corridors but warn the response is bottlenecked: a single mountain road serves the affected valleys, and uncoordinated private convoys are blocking heavy equipment. The UN logistics cluster has asked donors to route through its coordination cell.',
      'Early casualty figures vary across outlets — a normal pattern in the first days, as agents note. WeAware holds the toll at "800+ confirmed" and flags any precise higher figure as unverified until the civil protection agency’s next briefing.',
    ],
    consensus: 74,
    sources: [
      { outlet: 'Northbeam Post', stance: 'agree', note: 'Reports corridors, toll above 800, and the road bottleneck.' },
      { outlet: 'Meridian Wire', stance: 'agree', note: 'Quotes the logistics cluster on routing aid through coordination.' },
      { outlet: 'Harborlight Review', stance: 'context', note: '40,000 displaced; heavy equipment blocked by private convoys.' },
      { outlet: 'Social posts', stance: 'dispute', note: 'Precise higher tolls circulating are unverified pending official briefing.' },
    ],
    flaggedClaims: [
      {
        claim: 'Exact death tolls above 800 circulating online.',
        reason: 'Unverified until the civil protection agency’s next briefing; early figures normally vary.',
      },
    ],
    image: '/news/world-2.jpg',
    publishedAt: '10h ago',
    readMins: 4,
  },
  {
    id: 'world-election-observers',
    topic: 'World',
    title: 'Observer mission deploys early amid tight presidential race',
    summary:
      'International observers arrived six weeks before the presidential vote — unusually early — as polls show the top two candidates separated by two points.',
    body: [
      'An international observer mission deployed six weeks ahead of the presidential election, weeks earlier than standard practice, citing "heightened contestation risk" in what polls call a statistical tie.',
      'Both campaigns publicly welcomed the mission while privately briefing against it, according to two people familiar with the matter — the incumbent’s team calling it "performative," the challenger’s "insufficient." The mission will station long-term observers in all nine provinces.',
      'Coverage converges on the facts; the dispute is over significance. State media frames early deployment as routine cooperation, while independent outlets read it as a warning signal. Agents rate the "warning signal" reading as plausible but single-sourced.',
    ],
    consensus: 72,
    sources: [
      { outlet: 'Signal & Field', stance: 'agree', note: 'Reports the six-week-early deployment and nine-province coverage.' },
      { outlet: 'Meridian Wire', stance: 'context', note: 'Both campaigns welcome it publicly, brief against it privately.' },
      { outlet: 'State media', stance: 'dispute', note: 'Frames deployment as routine; timing is weeks ahead of standard practice.' },
      { outlet: 'Northbeam Post', stance: 'context', note: 'Polls show a two-point gap — a statistical tie.' },
    ],
    flaggedClaims: [
      {
        claim: 'Early deployment is "routine cooperation."',
        reason: 'Six weeks early is outside standard practice; the mission cited contestation risk.',
      },
    ],
    image: '/news/world-3.jpg',
    publishedAt: '12h ago',
    readMins: 4,
  },
  {
    id: 'good-library-of-things',
    topic: 'Good News',
    title: 'Library of Things lends 10,000th drill — repair cafés cut waste 34%',
    summary:
      'A neighbourhood lending library hit 10,000 loans as repair cafés report a third less household waste — all cross-checked with council data.',
    body: [
      'The Harborlight Library of Things recorded its 10,000th loan this week — a cordless drill borrowed for a fence repair — capping three years of growth from a single shipping container to six branches.',
      'Council waste data reviewed by WeAware agents shows participating postcodes sent 34% less bulky waste to landfill year-on-year, after adjusting for population growth. Auditors call the link "plausible and directionally consistent" rather than proven causal.',
      'Coverage is unusually consensual: all four outlets agree on the loan count and the waste figure, differing only on whether the model can replicate without grant funding.',
    ],
    consensus: 94,
    sources: [
      { outlet: 'Harborlight Review', stance: 'agree', note: 'Reports the 10,000th loan with branch-level counts.' },
      { outlet: 'Meridian Wire', stance: 'agree', note: 'Confirms the 34% waste figure from council datasets.' },
      { outlet: 'Ledgerline', stance: 'context', note: 'Notes grant funding covers 60% of operating costs.' },
      { outlet: 'Signal & Field', stance: 'context', note: 'Adds volunteer hours tripled to sustain opening times.' },
    ],
    flaggedClaims: [],
    image: '/news/climate-2.jpg',
    publishedAt: '2h ago',
    readMins: 3,
  },
  {
    id: 'good-school-streets',
    topic: 'Good News',
    title: 'Car-free school streets cut childhood asthma flare-ups by a fifth',
    summary:
      'Morning traffic bans outside 42 schools linked to 22% fewer asthma nurse visits — nurses, parents and traffic counts agree.',
    body: [
      'Nurse logs from 42 schools with morning car-free zones show 22% fewer asthma flare-up visits this term compared with the same term last year, according to a public-health analysis released Tuesday.',
      'Traffic sensors confirm car counts down 61% at drop-off, while control schools without bans show no change. Researchers caution the design is observational, but call the effect size "too large to dismiss as seasonal noise."',
      'Parents surveyed report children walking or wheeling to school up from 38% to 57%. All outlets corroborate the core numbers; one viral post claiming "asthma cured" was flagged as overstatement.',
    ],
    consensus: 89,
    sources: [
      { outlet: 'Northbeam Post', stance: 'agree', note: 'Reports the 22% figure with nurse-log methodology.' },
      { outlet: 'Harborlight Review', stance: 'agree', note: 'Confirms 61% traffic drop from sensor data.' },
      { outlet: 'Meridian Wire', stance: 'context', note: 'Notes the study is observational, not randomised.' },
      { outlet: 'Viral repost (social)', stance: 'dispute', note: 'Claims asthma "cured" — the paper reports fewer flare-ups, not a cure.' },
    ],
    flaggedClaims: [
      {
        claim: 'School bans "cured asthma."',
        reason: 'The study reports 22% fewer flare-up visits, not a cure. Effect is meaningful but limited.',
      },
    ],
    image: '/news/climate-1.jpg',
    publishedAt: '4h ago',
    readMins: 4,
  },
]
