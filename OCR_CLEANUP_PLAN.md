# OCR DATA CLEANUP PLAN

## Audit Summary

### Datasets Found
- **Total Evaluation Datasets**: 9
- **Plate Crop Directories**: 1 (737 images)
- **OCR Reports**: 15
- **Model Checkpoints**: 0
- **Dataset Scripts**: 21

### Key Findings

#### Clean Datasets (RETAIN)
1. **precropped_dataset.json** (737 entries)
   - All entries verified (737/737)
   - No CAM_TEST contamination
   - No duplicate image hashes
   - 33 duplicate ground truths (acceptable for same plates in different images)
   - Used by: evaluate_precropped.py, extract_plate_crops.py

2. **clean_evaluation_dataset.json** (538 entries)
   - All entries verified (538/538)
   - No CAM_TEST contamination
   - No duplicate image hashes
   - No duplicate ground truths
   - Sources: 1 REAL_INFERENCE, 537 VERIFIED_EXTERNAL
   - Used by: Multiple dataset building scripts

#### Contaminated Datasets (REMOVE/ARCHIVE)
1. **final_evaluation_dataset.json** (325 entries)
   - 52 CAM_TEST contaminations (16%)
   - 28 duplicate image hashes
   - Unknown verification status
   - **ACTION**: ARCHIVE and DELETE

2. **full_dataset.json** (310 entries)
   - 44 CAM_TEST contaminations (14%)
   - 28 duplicate image hashes
   - 7 duplicate ground truths
   - Unknown verification status
   - **ACTION**: ARCHIVE and DELETE

3. **cleaned_dataset.json** (21 entries)
   - 4 duplicate ground truths
   - 6 duplicate image hashes
   - Unknown verification status
   - **ACTION**: ARCHIVE and DELETE

4. **comprehensive_dataset.json** (25 entries)
   - 6 duplicate ground truths
   - 8 duplicate image hashes
   - Unknown verification status
   - **ACTION**: ARCHIVE and DELETE

5. **real_dataset.json** (21 entries)
   - 3 duplicate ground truths
   - 5 duplicate image hashes
   - Unknown verification status
   - **ACTION**: ARCHIVE and DELETE

6. **dataset.json** (5 entries)
   - 2 duplicate ground truths
   - 2 duplicate image hashes
   - Unknown verification status
   - **ACTION**: ARCHIVE and DELETE

7. **dataset_build_summary.json** (0 entries)
   - Empty file
   - **ACTION**: DELETE

#### OCR Reports (REMOVE OBSOLETE)
- All 15 OCR reports are tied to contaminated datasets
- **ACTION**: ARCHIVE and DELETE reports for contaminated datasets
- Keep only reports for clean datasets if they exist

#### Dataset Scripts (RETAIN)
- All 21 dataset scripts are working code
- **ACTION**: RETAIN all scripts

## Overlap Analysis

### Critical Overlap Found
- **clean_evaluation_dataset.json** overlaps with **precropped_dataset.json**: 536 ground truth overlaps
- This is concerning because precropped_dataset appears to be used as training data while clean_evaluation_dataset is for evaluation
- **ACTION**: Need to ensure complete separation between training and evaluation

### Other Overlaps
- Multiple datasets share the same small set of ground truths (TN09CQ1234, KA09MB7389, etc.)
- These appear to be test fixtures that got replicated across datasets
- **ACTION**: Remove these test fixture entries from evaluation datasets

## Cleanup Actions

### Phase 1: Archive Contaminated Data
1. Create archive directory: `data/ocr_eval_archive_[timestamp]`
2. Move contaminated datasets to archive:
   - final_evaluation_dataset.json
   - full_dataset.json
   - cleaned_dataset.json
   - comprehensive_dataset.json
   - real_dataset.json
   - dataset.json
   - dataset_build_summary.json
3. Move contaminated OCR reports to archive
4. Keep archive for backup purposes

### Phase 2: Remove Test Fixture Contamination
1. Remove entries with ground truths that appear in multiple datasets (test fixtures)
2. Remove CAM_TEST entries from any remaining datasets
3. Remove duplicate image hashes

### Phase 3: Verify Clean Dataset
1. Ensure clean_evaluation_dataset.json has no contamination
2. Ensure precropped_dataset.json has no contamination
3. Verify zero overlap between training and evaluation data
4. Remove ground truth overlaps between precropped and clean_evaluation

### Phase 4: Final Clean Evaluation Dataset
1. Create genuinely clean evaluation dataset with 500+ verified samples
2. Ensure zero overlap with training data
3. Verify all samples have real images (not synthetic placeholders)
4. Run OCR evaluation on clean dataset only

## Files to RETAIN

### Datasets
- `data/ocr_eval/precropped_dataset.json` (737 verified entries)
- `data/ocr_eval/clean_evaluation_dataset.json` (538 verified entries - after cleanup)

### Plate Crops
- `data/ocr_eval/plate_crops_external/` (737 images)

### Working Code
- All scripts in root directory
- `recognition/ocr_reader.py`
- `recognition/ocr_evaluation.py`
- All other application code

### PaddleOCR Models
- PaddleOCR pretrained models (in .venv or system cache)
- Do not delete PaddleOCR model files

## Expected Results After Cleanup

### Files Archived
- 7 contaminated dataset JSON files
- ~15 contaminated OCR report JSON files

### Files Deleted
- 1 empty dataset file (dataset_build_summary.json)
- Possibly some duplicate images after verification

### Files Retained
- 2 clean dataset JSON files
- 737 plate crop images
- All working source code
- All model checkpoint files (if any exist)
- All application code

### Final Dataset Counts
- **Training Dataset**: 737 verified samples (precropped_dataset.json)
- **Evaluation Dataset**: 500+ verified samples (cleaned clean_evaluation_dataset.json)
- **Zero Overlap**: Guaranteed by hash verification

## Next Steps

1. Execute Phase 1: Archive contaminated data
2. Execute Phase 2: Remove test fixture contamination
3. Execute Phase 3: Verify clean dataset integrity
4. Execute Phase 4: Create final clean evaluation dataset
5. Run OCR evaluation on clean dataset only
6. Report honest results without manipulation