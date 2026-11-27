# Matching evaluation

Run `python scripts/evaluate.py --matching-only` against a fresh temporary database. The first four cases also populate the public demo. The 26 additional fictional cases cover Czech and English BI, analytics, engineering, automation, Power Platform, Python and business analysis roles. Fit and skill labels were assigned from each description before running the scorer against the same fictional candidate.

The run matched 26 of 30 fit bands. Required skills had 81 true positives, zero false positives and zero false negatives. On the 26 cases labelled for preferred skills, there were 26 true positives, zero false positives and zero false negatives.

The descriptions use explicit requirement headings and known vocabulary. The results measure rubric agreement and extraction on this controlled dataset. They do not estimate generalization to real ads, eligibility decisions or interview outcomes. The evaluator can also exercise PDF export by omitting `--matching-only`.
