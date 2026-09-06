"""
tests/test_validate_dataset.py

Tests for detection/validate_dataset.py - the pre-training sanity checker
for a YOLO-format plate-detection dataset. No ultralytics/torch dependency
(the module under test only reads yaml/text/image files), so these run
anywhere pyyaml + opencv are available.
"""
import os
import shutil
import sys
import tempfile
import unittest

import numpy as np
import cv2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from detection.validate_dataset import validate_dataset  # noqa: E402


def _write_image(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cv2.imwrite(path, np.zeros((50, 50, 3), dtype=np.uint8))


def _write_label(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def _write_data_yaml(root, extra=""):
    with open(os.path.join(root, "data.yaml"), "w") as f:
        f.write(f"train: train/images\nval: valid/images\nnc: 1\nnames: ['license_plate']\n{extra}")


class TestValidateDataset(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_well_formed_dataset_passes(self):
        _write_data_yaml(self.tmp)
        _write_image(os.path.join(self.tmp, "train/images/a.jpg"))
        _write_label(os.path.join(self.tmp, "train/labels/a.txt"), "0 0.5 0.5 0.2 0.1\n")
        _write_image(os.path.join(self.tmp, "valid/images/b.jpg"))
        _write_label(os.path.join(self.tmp, "valid/labels/b.txt"), "0 0.5 0.5 0.2 0.1\n")

        self.assertTrue(validate_dataset(self.tmp))

    def test_missing_data_yaml_fails(self):
        self.assertFalse(validate_dataset(self.tmp))

    def test_missing_val_split_fails(self):
        _write_data_yaml(self.tmp)
        _write_image(os.path.join(self.tmp, "train/images/a.jpg"))
        _write_label(os.path.join(self.tmp, "train/labels/a.txt"), "0 0.5 0.5 0.2 0.1\n")
        # no valid/ folder at all

        self.assertFalse(validate_dataset(self.tmp))

    def test_pixel_coordinates_instead_of_normalized_fails(self):
        _write_data_yaml(self.tmp)
        _write_image(os.path.join(self.tmp, "train/images/a.jpg"))
        # 250 is not a valid normalized (0-1) coordinate - classic mistake
        _write_label(os.path.join(self.tmp, "train/labels/a.txt"), "0 250 180 60 30\n")
        _write_image(os.path.join(self.tmp, "valid/images/b.jpg"))
        _write_label(os.path.join(self.tmp, "valid/labels/b.txt"), "0 0.5 0.5 0.2 0.1\n")

        self.assertFalse(validate_dataset(self.tmp))

    def test_class_id_out_of_range_fails(self):
        _write_data_yaml(self.tmp)  # nc=1, so only class 0 is valid
        _write_image(os.path.join(self.tmp, "train/images/a.jpg"))
        _write_label(os.path.join(self.tmp, "train/labels/a.txt"), "5 0.5 0.5 0.2 0.1\n")
        _write_image(os.path.join(self.tmp, "valid/images/b.jpg"))
        _write_label(os.path.join(self.tmp, "valid/labels/b.txt"), "0 0.5 0.5 0.2 0.1\n")

        self.assertFalse(validate_dataset(self.tmp))

    def test_empty_label_file_is_treated_as_background_not_error(self):
        # a genuinely plate-free image with an empty label file is normal
        # (helps the model learn what "no plate" looks like) - must NOT
        # be flagged as broken.
        _write_data_yaml(self.tmp)
        _write_image(os.path.join(self.tmp, "train/images/a.jpg"))
        _write_label(os.path.join(self.tmp, "train/labels/a.txt"), "")
        _write_image(os.path.join(self.tmp, "valid/images/b.jpg"))
        _write_label(os.path.join(self.tmp, "valid/labels/b.txt"), "0 0.5 0.5 0.2 0.1\n")

        self.assertTrue(validate_dataset(self.tmp))

    def test_missing_label_file_warns_but_does_not_fail_alone(self):
        # a stray unlabeled image alone shouldn't fail the whole dataset -
        # it's a warning (could be intentional), not a structural break.
        _write_data_yaml(self.tmp)
        _write_image(os.path.join(self.tmp, "train/images/a.jpg"))
        _write_label(os.path.join(self.tmp, "train/labels/a.txt"), "0 0.5 0.5 0.2 0.1\n")
        _write_image(os.path.join(self.tmp, "train/images/unlabeled.jpg"))  # no .txt for this one
        _write_image(os.path.join(self.tmp, "valid/images/b.jpg"))
        _write_label(os.path.join(self.tmp, "valid/labels/b.txt"), "0 0.5 0.5 0.2 0.1\n")

        self.assertTrue(validate_dataset(self.tmp))


if __name__ == "__main__":
    unittest.main()
