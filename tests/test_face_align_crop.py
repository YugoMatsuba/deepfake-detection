import numpy as np

from ml import face_align_crop


class StubPart:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class StubShape:
    def __init__(self, mapping):
        self.mapping = mapping

    def part(self, idx):
        x, y = self.mapping[idx]
        return StubPart(x, y)


def test_get_five_keypoints_81_returns_deepfakebench_order():
    coords = {
        37: (10, 11),
        44: (20, 21),
        30: (30, 31),
        49: (40, 41),
        55: (50, 51),
    }
    shape = StubShape(coords)

    landmarks = face_align_crop.get_five_keypoints_81(shape)

    expected = np.array(
        [
            [10, 11],
            [20, 21],
            [30, 31],
            [40, 41],
            [50, 51],
        ],
        dtype=np.float32,
    )
    assert np.array_equal(landmarks, expected)


class Rect:
    def __init__(self, width, height):
        self._width = width
        self._height = height

    def width(self):
        return self._width

    def height(self):
        return self._height


def test_detect_largest_face_returns_max_area_face():
    faces = [Rect(5, 4), Rect(10, 2), Rect(6, 6)]

    class Detector:
        def __call__(self, rgb_image, upsample_factor):
            return faces

    largest = face_align_crop.detect_largest_face(Detector(), np.zeros((2, 2, 3), dtype=np.uint8))

    assert largest is faces[2]


def test_detect_largest_face_returns_none_when_no_faces():
    class Detector:
        def __call__(self, rgb_image, upsample_factor):
            return []

    assert face_align_crop.detect_largest_face(Detector(), np.zeros((2, 2, 3), dtype=np.uint8)) is None


def test_align_and_crop_rgb_returns_none_when_detector_finds_no_faces(monkeypatch):
    monkeypatch.setattr(face_align_crop, "detect_largest_face", lambda *args, **kwargs: None)

    class FailingPredictor:
        def __call__(self, *args, **kwargs):
            raise AssertionError("predictor should not run when no faces are detected")

    result = face_align_crop.align_and_crop_rgb(
        np.zeros((8, 8, 3), dtype=np.uint8),
        detector=object(),
        predictor=FailingPredictor(),
    )

    assert result is None
