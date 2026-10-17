# Evaluation report

Training writes classifier results to `artifacts/metrics.json`; OCR evaluation writes results to `artifacts/ocr_metrics.json` and per-image details to `data/ocr_results.csv`.

## Dataset and method
- Source: Hugging Face `BEE-spoke-data/consumer-finance-complaints`, `has-text` config (CFPB-derived February 2024 snapshot)
- Sample size: see metrics JSON (default 15,000)
- Split: 80% training / 20% held-out test; training subset used for validation threshold selection
- Label: Product; text: non-empty narrative only
- Rare classes: fewer than 50 training examples mapped to `Other / rare product`
- Seed: 42

## Classifier results
- Test accuracy: 71.3%
- Test macro-F1: 0.474
- Test weighted-F1: 0.702
- Test auto-route coverage: 56.9%
- Accuracy among auto-routed test rows: 84.2%
- Selected threshold: 0.575

Validation selected the threshold with maximum auto-route coverage while meeting at least 85% accuracy: 52.3% validation coverage at 85.5% accuracy. Held-out accuracy among auto-routed cases was 84.2%, so the validation target did not fully generalize.

### Per-class test F1

| Product label | F1 | Support |
|---|---:|---:|
| Bank account or service | 0.121 | 28 |
| Checking or savings account | 0.713 | 162 |
| Consumer Loan | 0.118 | 15 |
| Credit card | 0.151 | 63 |
| Credit card or prepaid card | 0.609 | 188 |
| Credit reporting | 0.205 | 56 |
| Credit reporting or other personal consumer reports | 0.406 | 211 |
| Credit reporting, credit repair services, or other personal consumer reports | 0.808 | 1432 |
| Debt collection | 0.729 | 422 |
| Money transfer, virtual currency, or money service | 0.656 | 65 |
| Mortgage | 0.848 | 196 |
| Other / rare product | 0.000 | 15 |
| Payday loan, title loan, or personal loan | 0.528 | 31 |
| Student loan | 0.754 | 71 |
| Vehicle loan or lease | 0.467 | 45 |

### Confusion matrix

Rows are true labels and columns are predicted labels. Both use this order:
0. Bank account or service
1. Checking or savings account
2. Consumer Loan
3. Credit card
4. Credit card or prepaid card
5. Credit reporting
6. Credit reporting or other personal consumer reports
7. Credit reporting, credit repair services, or other personal consumer reports
8. Debt collection
9. Money transfer, virtual currency, or money service
10. Mortgage
11. Other / rare product
12. Payday loan, title loan, or personal loan
13. Student loan
14. Vehicle loan or lease

```text
2, 20, 0, 0, 3, 0, 0, 0, 2, 0, 1, 0, 0, 0, 0
1, 138, 0, 1, 13, 0, 0, 2, 0, 7, 0, 0, 0, 0, 0
0, 2, 1, 1, 2, 0, 0, 0, 1, 0, 1, 0, 0, 1, 6
0, 3, 0, 7, 40, 0, 1, 8, 4, 0, 0, 0, 0, 0, 0
0, 17, 0, 8, 134, 0, 0, 10, 13, 2, 1, 0, 0, 0, 3
1, 0, 0, 1, 1, 8, 0, 42, 2, 0, 0, 0, 0, 1, 0
0, 2, 0, 2, 1, 0, 83, 111, 10, 0, 1, 0, 0, 0, 1
1, 11, 0, 4, 31, 14, 108, 1135, 90, 1, 17, 1, 1, 11, 7
0, 6, 0, 5, 14, 0, 4, 50, 326, 1, 10, 0, 1, 1, 4
0, 16, 0, 0, 5, 0, 0, 2, 0, 40, 1, 0, 1, 0, 0
0, 2, 0, 0, 1, 0, 0, 5, 8, 1, 178, 0, 1, 0, 0
0, 3, 0, 1, 4, 0, 0, 1, 1, 3, 0, 0, 2, 0, 0
0, 1, 0, 0, 2, 0, 0, 2, 2, 2, 6, 0, 14, 0, 2
0, 3, 0, 0, 0, 0, 0, 2, 7, 0, 4, 0, 2, 52, 1
0, 1, 1, 0, 1, 0, 2, 8, 6, 0, 4, 0, 0, 1, 21
```

## Threshold rationale
Validation threshold sweep covers 0.20–0.95. Choose the highest-coverage threshold with at least 85% validation accuracy among auto-routed examples. Report held-out test coverage and accuracy separately; this is a target, not a production guarantee.

## OCR results
Run `python -m scripts.evaluate_ocr`; it evaluates 20 held-out complaints rendered cleanly and with downscaling, blur and rotation. Each mode contains 20 images.
- Clean mean CER: 14.80%
- Noisy mean CER: 81.85%
- Clean routing agreement with original-text prediction: 85.0%
- Noisy routing agreement with original-text prediction: 35.0%
- Clean routing accuracy vs true label: 65.0%
- Noisy routing accuracy vs true label: 45.0%
- Mean OCR confidence, clean/noisy: 65.70 / 30.26

CER = (substitutions + deletions + insertions) / number of ground-truth characters. OCR confidence below 45 triggers review.

## Three observed failures
Examples below are from the 20-row held-out OCR fixture; identifying details are redacted in the source narratives.
1. **Ambiguous account vs. transfer wording (fixture example 1, original text).** True label: `Checking or savings account`; predicted: `Money transfer, virtual currency, or money service`. The narrative describes a Wells Fargo-linked third-party deposit for a purchase. Deposit and third-party wording overlaps account and money-transfer products, and the model chose the latter.
2. **Underrepresented overlapping credit-report label (fixture example 5, original text).** True label: `Credit reporting, credit repair services, or other personal consumer reports`; predicted: `Credit reporting`. The narrative concerns requesting an annual report from one of the three bureaus. The predicted `Credit reporting` class had only 56 test examples and F1 0.205, versus 1,432 examples and F1 0.808 for the closely related true class. Similar wording plus the historical label split contributes to confusion.
3. **Noisy OCR changes the route (fixture example 3).** True and original-text prediction: `Debt collection`; noisy OCR prediction: `Credit reporting`. The complaint describes a company reporting an alleged debt and requests an audit trail. In the noisy image, OCR produced mostly corrupted text (CER 83.83%), losing the collection context and changing the predicted department.

## Interpretation
The CFPB dataset concerns consumer finance, not the full range of public grievances. Results do not establish readiness for a real state portal without local training data, validation, and officer oversight. Noisy OCR performance is particularly weak: mean CER is 81.85%, and only 35% of OCR predictions match the original-text predictions in this 20-complaint test.
