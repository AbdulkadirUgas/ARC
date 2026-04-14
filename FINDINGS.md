# ARC Findings Summary

## What Was Done

1. The dataset was analyzed and split with a multi-label taxonomy.
2. Multiple baseline families were tested, including Qwen prompt runs, deterministic solvers, object-program solvers, and compositional search solvers.
3. The results were normalized into a shareable dashboard.

## Main Findings

- ARC is not one uniform category of problem.
- Easier families such as crop/extract and simple transform or color-map tasks show some signal with simple baselines.
- Hard object/compositional reasoning remains the weakest region.
- Qwen prompt baselines improved output formatting in some runs, but did not produce meaningful exact solves on evaluation.
- Deterministic and object/compositional search baselines showed some useful signal on easier subsets, but still broke on the hard object-compositional evaluation categories.

## Practical Conclusion

- Synthetic data should be targeted toward the weak categories rather than generated uniformly across all task families.
- The highest-value synthetic focus is hard object/compositional reasoning.
- Another round of simple prompt-only testing is unlikely to help much.
- The next solver direction should be stronger program or rule search for object-compositional reasoning.

## Shareable Dashboard

The public summary dashboard lives in `docs/index.html` and is intended for GitHub Pages.
