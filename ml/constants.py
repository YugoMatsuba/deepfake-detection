# constants.py  DeepfakeBench-aligned, repo-relative paths

import os
import numpy as np

# ===== Core Processing Constants (from all configs) =====
FRAME_NUM: int = 32                    # frame_num: {'test': 32}
IMG_SIZE: int = 256                    # resolution: 256  
MEAN = (0.5, 0.5, 0.5)                # mean: [0.5, 0.5, 0.5]
STD = (0.5, 0.5, 0.5)                 # std: [0.5, 0.5, 0.5]

# ===== Processing Policies (deterministic, DB-aligned) =====
SAMPLING_METHOD = "uniform_linspace"   # Fixed 32-frame sampling via np.linspace
DROP_FRAMES_WITHOUT_FACE = True       # Skip frames with no detected face
PAD_LAST_IF_SHORT = True              # Repeat last valid crop until 32 frames
KEEP_RGB_FOR_INFERENCE = True         # Aligned crops stay RGB (convert BGR only for debug saves)

# ===== Face Alignment Constants (from preprocess.py) =====
ALIGN_SCALE: float = 1.3              # scale parameter in img_align_crop
ALIGN_OUTPUT_SIZE = (IMG_SIZE, IMG_SIZE)  # outsize=(256, 256)

# 5-point template in 112�112 space (from DeepfakeBench preprocess.py)
DST_5PTS_112 = np.array([
    [30.2946, 51.6963],  # left eye
    [65.5318, 51.5014],  # right eye
    [48.0252, 71.7366],  # nose  
    [33.5493, 92.3655],  # left mouth
    [62.7299, 92.2041]], dtype=np.float32)  # right mouth

# ===== Model Specifications =====
MODEL_XCEPTION = "xception"
MODEL_SPSL = "spsl"
MODEL_UCF = "ucf"

NUM_CLASSES = 2                       # backbone_config: num_classes: 2
FAKE_CLASS_INDEX = 1                  # torch.softmax(pred, dim=1)[:, 1]

XCEPTION_INPUT_CHANNELS = 3           # RGB
SPSL_INPUT_CHANNELS = 4               # RGB + Phase (inc: 4 in spsl.yaml)
UCF_INPUT_CHANNELS = 3                # RGB
UCF_ENCODER_FEAT_DIM = 512            # encoder_feat_dim: 512 in ucf.yaml  
UCF_USE_SHARED_HEAD = True            # Inference uses head_sha (shared head)

# ===== Weight Files =====
DEFAULT_WEIGHTS = {
    MODEL_XCEPTION: "xception_best.pth",
    MODEL_SPSL: "spsl_best.pth",
    MODEL_UCF: "ucf_best.pth",
}

DLIB_PREDICTOR_FILENAME = "shape_predictor_81_face_landmarks.dat"

# ===== Repo-Relative Paths + Env Overrides =====
# Get the directory containing this constants.py file (ml/)
_CONSTANTS_DIR = os.path.dirname(os.path.abspath(__file__))

# Default paths relative to ml/ directory
DEFAULT_WEIGHTS_DIR = os.path.join(_CONSTANTS_DIR, "weights")
DEFAULT_DLIB_DIR = os.path.join(_CONSTANTS_DIR, "dlib") 
DEFAULT_DATA_DIR = os.path.join(_CONSTANTS_DIR, "data")

# Environment variable overrides
def get_weights_dir(): 
    return os.environ.get("ML_WEIGHTS_DIR", DEFAULT_WEIGHTS_DIR)

def get_dlib_dir(): 
    return os.environ.get("ML_DLIB_DIR", DEFAULT_DLIB_DIR)

def get_data_dir(): 
    return os.environ.get("ML_DATA_DIR", DEFAULT_DATA_DIR)

def get_dlib_predictor_path(): 
    return os.path.join(get_dlib_dir(), DLIB_PREDICTOR_FILENAME)

# ===== Validation Guards =====
assert FRAME_NUM == 32, "Must remain 32 to match DeepfakeBench test frame count"
assert IMG_SIZE == 256, "Must remain 256 to match DeepfakeBench resolution"
assert len(DST_5PTS_112) == 5, "Must have exactly 5 facial landmark points"
