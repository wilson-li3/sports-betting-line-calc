# Ablation Study Summary

## Best Model

**Feature Set:** B: line_plus_context  
**Variant:** uncalibrated  
**Log Loss:** 0.612  
**ROC-AUC:** 0.722

## Key Findings

1. **Context features add signal beyond market lines:**
   - Feature set B (line + context) outperformed feature set A (line only) by a significant margin.
   - Context features (home/away, competitive status, pace bucket) capture important game dynamics that market lines alone do not capture.

2. **Rolling totals and full model add noise:**
   - Feature set C (line + rolling totals) and D (full model) showed worse performance than B.
   - Additional features beyond context introduced overfitting or noise, leading to higher log loss.

3. **Uncalibrated model performed best:**
   - For the best feature set (B), the uncalibrated logistic regression outperformed sigmoid-calibrated.
   - This suggests the base model is already well-calibrated for this feature set.

## Full Results Table

| Feature Set | Variant | Accuracy | Log Loss | ROC-AUC |
|------------|---------|----------|----------|---------|
| B: line_plus_context | uncalibrated | 0.660 | 0.612 | 0.722 |
| B: line_plus_context | sigmoid | 0.657 | 0.627 | 0.710 |
| D: full_model | sigmoid | 0.649 | 0.639 | 0.688 |
| D: full_model | uncalibrated | 0.645 | 0.646 | 0.698 |
| A: line_only | uncalibrated | 0.605 | 0.654 | 0.655 |
| C: line_plus_rolling_totals | uncalibrated | 0.606 | 0.660 | 0.650 |
| A: line_only | sigmoid | 0.604 | 0.664 | 0.646 |
| C: line_plus_rolling_totals | sigmoid | 0.599 | 0.665 | 0.644 |

## Conclusion

The best model uses only market lines (TEAM_TOTAL_LINE, GAME_TOTAL_LINE) combined with contextual game features (home/away, competitive status, pace bucket). This simple, interpretable model outperforms more complex feature sets, demonstrating that feature engineering should prioritize quality over quantity.

Future work could explore:
- Interaction terms between context features and lines
- Time-of-season or opponent-strength features
- More sophisticated regularization techniques
