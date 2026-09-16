# Saved growth baseline — 2026-09-16

Reproduce with:

```bash
python3 growth_report.py --as-of 2026-09-16T00:00:00Z --days 30
```

Source: local `public/post_ledger.json`, 150 retained entries; latest post in the
file is 2026-09-15. No live account metrics or eligibility checks were performed.

| Observation | Value | Sample |
| --- | ---: | ---: |
| Eligible posts in 30-day window | 64 | Local ledger |
| Valid mature snapshots | 56 | Collected at age 48h–7d |
| Missing/invalid mature snapshots | 8 | Unknown, not zero |
| Median views | 7 | 56 |
| Median absolute watch seconds | 1.22 | 13 with at least 20 views and watch data |
| Median shares per 1,000 reached | 0 | 12 above view/reach floors with metric |
| Median saves per 1,000 reached | 0 | 12 above view/reach floors with metric |
| Posts with observed saves/shares above exposure floors | 0 | Those eligible observations |
| Median snapshot collection age | 67.53 hours | 56 |

43 mature snapshots have fewer than 20 views (or no usable view count), so they
do not contribute to quality medians. The window has too little adequately
exposed quality data to choose a winning series. Among mature snapshots, the
initial title classifier matches 3 tool stories and 1 reliability/security
story; 52 remain unclassified. That is a narrow vocabulary proxy and may miss
relevant stories. It does not prove those 52 posts attracted the wrong people.

No runtime experiment tags are present in this report window. The report cannot
claim a short/long winner, and this implementation does not start an experiment.

Interpretation: the saved data shows low distribution and very short observed
attention. Test a clearer recurring audience promise and earlier useful proof.
Do not infer a restriction, exact audience demographics, or a causal diagnosis
from these numbers. New growth metadata makes the rollout visible in subsequent
reports, but a before/after comparison remains observational.
