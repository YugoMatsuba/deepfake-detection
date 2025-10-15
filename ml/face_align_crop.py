# face_align_crop.py - DeepfakeBench-aligned face detection and alignment

import cv2
import dlib
import numpy as np
from skimage import transform as trans
from . import constants


def get_five_keypoints_81(dlib_shape):
    """
    Extract 5 key facial landmarks from 81-point dlib predictor.
    Uses exact DeepfakeBench indices for compatibility.
    
    Args:
        dlib_shape: dlib.full_object_detection from 81-point predictor
        
    Returns:
        np.array: 5x2 array of (x,y) coordinates for [left_eye, right_eye, nose, left_mouth, right_mouth]
    """
    # DeepfakeBench landmark indices for 81-point predictor
    left_eye = np.array([dlib_shape.part(37).x, dlib_shape.part(37).y]).reshape(-1, 2)
    right_eye = np.array([dlib_shape.part(44).x, dlib_shape.part(44).y]).reshape(-1, 2)  
    nose = np.array([dlib_shape.part(30).x, dlib_shape.part(30).y]).reshape(-1, 2)
    left_mouth = np.array([dlib_shape.part(49).x, dlib_shape.part(49).y]).reshape(-1, 2)
    right_mouth = np.array([dlib_shape.part(55).x, dlib_shape.part(55).y]).reshape(-1, 2)
    
    # Concatenate to 5x2 array
    landmarks = np.concatenate([left_eye, right_eye, nose, left_mouth, right_mouth], axis=0)
    return landmarks.astype(np.float32)


def detect_largest_face(detector, rgb_image, upsample_factor=1):
    """
    Find largest face rectangle using dlib detector.
    
    Args:
        detector: dlib face detector
        rgb_image: Input image in RGB format
        upsample_factor: Upsample factor for detection (default 1, like DeepfakeBench)
        
    Returns:
        dlib.rectangle: Largest face rectangle or None if no faces detected
    """
    faces = detector(rgb_image, upsample_factor)
    if len(faces) == 0:
        return None
        
    # Find largest face by area
    largest_face = max(faces, key=lambda rect: rect.width() * rect.height())
    return largest_face


def align_and_crop_rgb(img_rgb, detector, predictor, outsize=(constants.IMG_SIZE, constants.IMG_SIZE), scale=constants.ALIGN_SCALE):
    """
    Align and crop face following DeepfakeBench's exact methodology.
    
    This function replicates the alignment sequence from DeepfakeBench preprocessing:
    1. BGR -> RGB conversion
    2. Largest face detection  
    3. 5-point landmark extraction (indices 37,44,30,49,55)
    4. Template construction with +8.0 horizontal shift
    5. Scaling to output size with margin logic
    6. SimilarityTransform estimation and warping
    
    Args:
        img_rgb: Input image in RGB format
        detector: dlib face detector
        predictor: dlib 81-point shape predictor
        outsize: Output size tuple, default (256, 256)
        scale: Margin scale factor, default 1.3 (matches DeepfakeBench)
        
    Returns:
        np.ndarray: RGB 256�256 aligned face crop, or None if no face detected
    """
    # Step 1: Use RGB input directly (already converted in video_io.py)
    rgb = img_rgb
    
    # Step 2: Find largest face
    largest_face = detect_largest_face(detector, rgb, upsample_factor=1)
    if largest_face is None:
        return None
        
    # Step 3: Extract 5-point landmarks using DeepfakeBench indices
    shape = predictor(rgb, largest_face)
    landmarks = get_five_keypoints_81(shape)
    
    # Step 4: Build alignment template (exact DeepfakeBench sequence)
    dst = constants.DST_5PTS_112.copy()  # Start with base unshifted template
    target_size = [112, 112]
    
    # Apply +8.0 horizontal shift (always triggered in DeepfakeBench)
    if target_size[1] == 112:
        dst[:, 0] += 8.0
        
    # Scale template coordinates to output size  
    dst[:, 0] = dst[:, 0] * outsize[0] / target_size[0]
    dst[:, 1] = dst[:, 1] * outsize[1] / target_size[1]
    
    target_size = outsize
    
    # Step 5: Apply margin logic with scale factor
    margin_rate = scale - 1
    x_margin = target_size[0] * margin_rate / 2.
    y_margin = target_size[1] * margin_rate / 2.
    
    # Move template points to account for margin
    dst[:, 0] += x_margin
    dst[:, 1] += y_margin
    
    # Resize coordinates to compensate for margin
    dst[:, 0] *= target_size[0] / (target_size[0] + 2 * x_margin)
    dst[:, 1] *= target_size[1] / (target_size[1] + 2 * y_margin)
    
    # Step 6: Estimate similarity transform and warp
    src = landmarks.astype(np.float32)
    
    # Use skimage SimilarityTransform with all 5 points (like DeepfakeBench)
    tform = trans.SimilarityTransform()
    tform.estimate(src, dst)
    M = tform.params[0:2, :]  # Extract 2x3 affine matrix
    
    # Warp image using the transform matrix
    aligned = cv2.warpAffine(rgb, M, (target_size[1], target_size[0]))
    
    # Guard resize to exact output size (matches DeepfakeBench behavior)
    if outsize is not None:
        aligned = cv2.resize(aligned, (outsize[1], outsize[0]))
        
    return aligned  # Return RGB crop (no BGR conversion for inference)


def create_dlib_detector_and_predictor(predictor_path=None):
    """
    Create dlib face detector and 81-point shape predictor.
    
    Args:
        predictor_path: Path to shape_predictor_81_face_landmarks.dat file.
                       If None, uses constants.get_dlib_predictor_path()
                       
    Returns:
        tuple: (dlib.get_frontal_face_detector(), dlib.shape_predictor)
        
    Raises:
        FileNotFoundError: If predictor file does not exist
    """
    if predictor_path is None:
        predictor_path = constants.get_dlib_predictor_path()
    
    # Check if predictor file exists
    import os
    if not os.path.exists(predictor_path):
        raise FileNotFoundError(f"Dlib predictor file not found at: {predictor_path}")
        
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(predictor_path)
    
    return detector, predictor
