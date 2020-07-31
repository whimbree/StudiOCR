
import cv2
import numpy as np
from typing import Union

# IMAGE PREPROCESSING
def grayscale_flat_field_correction(src: np.ndarray, ksize: int = 99) -> np.ndarray:
    image_grayscale = src if src.ndim == 2 else cv2.cvtColor(src=src, code=cv2.COLOR_BGR2GRAY)
    blur = cv2.medianBlur(src=image_grayscale, ksize=ksize)
    mean = cv2.mean(src=blur)[0]

    # It's fine if we divide by zero
    with np.errstate(divide='ignore', invalid='ignore'):
        flat_field = (image_grayscale * mean) / blur
    return flat_field

# SCORING

def levenshtein(s1, s2):
    if len(s1) < len(s2):
        return levenshtein(s2, s1)

    # len(s1) >= len(s2)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[
                             j + 1] + 1  # j+1 instead of j since previous_row and current_row are one character longer
            deletions = current_row[j] + 1  # than s2
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]

def zero_one_loss(text_exp: np.ndarray, text_pred: np.ndarray, tol: Union[int, float]=0.2) -> float:
    """
    Computes accuracy of predicted texts

    Parameters
    text_exp - true texts found in image by human eyesight
    text_pred - predicted texts picked up by pytesseract
    tol - tolerance in terms of maximum allowed levenshtein distance
    """
    # Error checking for valid arguments
    # try:
    #     if text_exp is None or text_pred is None:
    #         raise ValueError('arguments cannot be None')
    #     if text_exp.ndim != 1 or text_pred.ndim != 1:
    #         raise ValueError('arguments must be both 1-D')
    #     if text_exp.size == 0:
    #         raise ValueError('there must be at least one expected text in text_exp')
    # except ValueError as error:
    #     print(str(error))
    #     return

    text_exp_set = set(text_exp)
    correct_counter = 0
    if isinstance(tol, int):
        # Absolute tolerance, regardless of text length
        for s1 in text_pred:
            # For very short text
            if len(s1) <= 3 and np.any(a=[s1 in text_exp_set]):
                correct_counter += 1
            elif np.any(a=[levenshtein(s1=s1, s2=s2) <= tol for s2 in text_exp_set], axis=None):
                correct_counter += 1
    else:
        # Adaptive tolerance, where allowable levenshtein distance is proportional to predicted text length
        for s1 in text_pred:
            # For very short text
            if len(s1) <= 3 and np.any(a=[s1 in text_exp_set]):
                correct_counter += 1
            elif np.any(a=[levenshtein(s1=s1, s2=s2) <= int(tol * len(s1)) for s2 in text_exp_set], axis=None):
                correct_counter += 1
    return correct_counter / len(text_exp_set)
