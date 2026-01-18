# Ablation Study Summary

## Best Model

**Feature Set:** B: line_plus_context  
**Variant:** uncalibrated  
**Log Loss:** 0.611  
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
| B: line_plus_context | uncalibrated | 0.661 | 0.611 | 0.722 |
| B: line_plus_context | sigmoid | 0.656 | 0.627 | 0.710 |
| D: full_model | sigmoid | 0.653 | 0.639 | 0.688 |
| D: full_model | uncalibrated | 0.648 | 0.647 | 0.697 |
| A: line_only | uncalibrated | 0.605 | 0.654 | 0.656 |
| C: line_plus_rolling_totals | uncalibrated | 0.604 | 0.659 | 0.650 |
| A: line_only | sigmoid | 0.599 | 0.664 | 0.644 |
| C: line_plus_rolling_totals | sigmoid | 0.595 | 0.665 | 0.642 |

## Conclusion

The best model uses only market lines (TEAM_TOTAL_LINE, GAME_TOTAL_LINE) combined with contextual game features (home/away, competitive status, pace bucket). This simple, interpretable model outperforms more complex feature sets, demonstrating that feature engineering should prioritize quality over quantity.

Future work could explore:
- Interaction terms between context features and lines
- Time-of-season or opponent-strength features
- More sophisticated regularization techniques
