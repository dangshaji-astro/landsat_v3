# Landslide RF Model — Accuracy Improvement Tasks

Context: Kerala landslide risk pipeline. Current features: `dem_avg`, `slope_avg`, `slope_max`, USDA soil texture class, `rain7` (7-day rainfall sum), SWI (exponential decay soil water index, factor 0.85). Model: `landslide_rf_model.pkl` (sklearn RandomForestClassifier). Grid: 39,853 cells, 1km resolution, clipped to Kerala.

Work through tasks in order. Each task is independent enough to run as its own step; report results (metric deltas) after each before moving to the next.

## Task 1 — Audit training data
1. Load the training dataset used for `landslide_rf_model.pkl`.
2. Report: total rows, count of positive (landslide) vs negative (no landslide) samples, class ratio.
3. Report how negative samples were selected (random across Kerala vs terrain-matched).
4. Flag if positive sample count < 300 or class ratio worse than 1:10 — these are red flags for reliability.

## Task 2 — Fix evaluation methodology
1. Check whether current validation uses random k-fold CV or spatial CV.
2. If random k-fold: implement spatial block cross-validation (hold out contiguous geographic regions, not random rows) using the grid cell lat/lon to define blocks.
3. Re-evaluate the existing model under spatial CV and report precision, recall, F1, and PR-AUC (not plain accuracy) — this is the true baseline.

## Task 3 — Rebalance classes
1. Set `class_weight='balanced'` on the RandomForestClassifier (or apply SMOTE on the minority class).
2. Retrain, re-evaluate under the same spatial CV split as Task 2.
3. Report metric delta vs Task 2 baseline.

## Task 4 — Add terrain features (derive from existing SRTM DEM in GEE)
Add these per-cell features, then retrain and re-evaluate:
1. Plan curvature and profile curvature
2. Topographic Wetness Index (TWI)
3. Aspect (slope direction, categorical or sin/cos encoded)
4. Distance to nearest drainage/stream line
Report feature importances after retraining to see which of these matter.

## Task 5 — Add land cover feature
1. Pull Sentinel-2 or ESA WorldCover land use/land cover classification per cell from GEE.
2. Add as categorical feature (forest / cropland / bare / built-up / etc).
3. Retrain, re-evaluate, report delta.

## Task 6 — Expand rainfall features
1. Instead of a single blended SWI, compute antecedent rainfall sums for multiple windows separately: 3-day, 7-day, 15-day, 30-day.
2. Add peak rainfall intensity (max mm/hr or max daily mm in the lookback window) as a separate feature.
3. Retrain with all rainfall features included individually (don't pre-blend), re-evaluate, report delta and feature importances.

## Task 7 — Model comparison
1. Train XGBoost and/or LightGBM classifiers on the same final feature set from Task 6.
2. Compare against the RandomForest under identical spatial CV splits.
3. Report which model wins on PR-AUC and recall (recall matters most — missing a real landslide is worse than a false alarm).

## Task 8 — Hyperparameter tuning
1. On the winning model from Task 7, run a grid/random search over key params (for RF: `n_estimators`, `max_depth`, `min_samples_leaf`; for XGBoost: `max_depth`, `learning_rate`, `n_estimators`, `subsample`).
2. Use spatial CV for scoring during search, not random CV.
3. Report best params and final metrics.

## Task 9 — Ground-truth sanity check
1. Get coordinates of known historical landslide events (Wayanad 2024, Idukki 2018/2019, or any available GSI Bhukosh inventory points).
2. Run the final model on those cells and report what risk category (LOW/MEDIUM/HIGH) each was assigned.
3. Flag any known-landslide cell that comes out LOW — that's a false negative worth investigating.

## Deliverable
A short report (markdown) summarizing: baseline vs final metrics (precision/recall/PR-AUC), which features had the highest importance, and results of the ground-truth sanity check.
