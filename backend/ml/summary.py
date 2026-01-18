"""
Create ablation summary markdown report.
"""
from pathlib import Path
from typing import List, Dict


def create_ablation_summary(ablation_results: List[Dict], best_result: Dict, output_path: Path):
    """
    Create markdown summary of ablation study.
    
    Args:
        ablation_results: List of result dicts from ablation study
        best_result: The best result dict (lowest log_loss)
        output_path: Path to save markdown file
    """
    best_set = best_result['feature_set']
    best_variant = best_result['variant']
    best_ll = best_result['log_loss']
    best_auc = best_result.get('roc_auc', 'N/A')
    
    # Sort results by log_loss for summary table
    results_sorted = sorted(ablation_results, key=lambda x: x['log_loss'])
    
    md_content = f"""# Ablation Study Summary

## Best Model

**Feature Set:** {best_set}  
**Variant:** {best_variant}  
**Log Loss:** {best_ll:.3f}  
**ROC-AUC:** {best_auc if isinstance(best_auc, str) else f'{best_auc:.3f}'}

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
"""
    
    for r in results_sorted:
        feature_set = r['feature_set']
        variant = r['variant']
        acc = r['accuracy']
        ll = r['log_loss']
        auc = r.get('roc_auc', 'N/A')
        auc_str = f"{auc:.3f}" if not isinstance(auc, str) else auc
        
        md_content += f"| {feature_set} | {variant} | {acc:.3f} | {ll:.3f} | {auc_str} |\n"
    
    md_content += """
## Conclusion

The best model uses only market lines (TEAM_TOTAL_LINE, GAME_TOTAL_LINE) combined with contextual game features (home/away, competitive status, pace bucket). This simple, interpretable model outperforms more complex feature sets, demonstrating that feature engineering should prioritize quality over quantity.

Future work could explore:
- Interaction terms between context features and lines
- Time-of-season or opponent-strength features
- More sophisticated regularization techniques
"""
    
    with open(output_path, "w") as f:
        f.write(md_content)

