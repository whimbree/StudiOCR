import cv2
import pytesseract
from pytesseract import Output

# This entire file must be redone with objects
# This is just a quick demo to show how to get started with OCR
# References:
# https://nanonets.com/blog/ocr-with-tesseract/
# https://pypi.org/project/pytesseract/


def resize_keep_aspect_ratio(image, width=None, height=None, inter=cv2.INTER_AREA):
    new_dim = None
    h, w = image.shape[:2]

    if width is None and height is None:
        return image
    elif width is None:
        ratio = height / h
        new_dim = (int(w * ratio), height)
    else:
        ratio = width / w
        new_dim = (width, int(h * ratio))

    return cv2.resize(image, new_dim, interpolation=inter)


def process_image(image) -> dict:
    # Maybe further postprocessing is needed for a better result
    custom_config = r'-l eng --psm 3 --tessdata-dir "tessdata_fast"'
    return pytesseract.image_to_data(
        img, config=custom_config, output_type=Output.DICT)


img = cv2.imread("test_img/conv_props.jpg")
img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

img_ocr = process_image(img)
print(img_ocr['text'])

for i in range(len(img_ocr['text'])):
    if len(img_ocr['text'][i]) != 0:
        (x, y, w, h) = (img_ocr['left'][i], img_ocr['top']
                        [i], img_ocr['width'][i], img_ocr['height'][i])
        img = cv2.rectangle(img, (x, y), (x + w, y + h), (255, 0, 0), 2)


img_small = resize_keep_aspect_ratio(img, height=1000)
# Show the image after bounding boxes placed over detected words
cv2.imshow('img', img_small)
cv2.waitKey(1)

# Loop forever so that the image is still shown for testing purposes
# Ctrl+C in terminal to kill the program
while True:
    pass
