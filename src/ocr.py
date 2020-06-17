import cv2
import pytesseract
from pytesseract import Output

from db import *

# This entire file must be redone with objects
# This is just a quick demo to show how to get started with OCR
# References:
# https://nanonets.com/blog/ocr-with-tesseract/
# https://pypi.org/project/pytesseract/


# This class will process a multi page document as images and then store it in the database
class OcrProcess():
    def __init__(self, name: str):
        self._name = name
        self._data = list()

    def process_image(self, image_filepath: str):
        # Maybe further postprocessing is needed for a better result
        # TODO: allow users to specify a custom config?
        # TODO: allow users to specify fast vs. best models
        custom_config = r'-l eng --psm 6 --tessdata-dir "../tessdata/best"'
        image = cv2.imread(image_filepath)
        # Convert to RGB colorspace for Tesseract OCR
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        page_data = pytesseract.image_to_data(
            image, config=custom_config, output_type=Output.DICT)
        image_file = open(image_filepath, 'rb')
        self._data.append((page_data, image_file.read()))

    def commit_data(self):
        # If the database doesn't exist yet, generate it
        create_tables()
        with db.atomic():
            # Create a new entry for the document to link the pages and boxes to
            doc = OcrDocument.create(name=self._name)
            for i, (page_data, image_file) in enumerate(self._data):
                page = OcrPage.create(
                    number=i, image=image_file, document=doc.id)
                for i in range(len(page_data)):
                    text_nospace = page_data['text'][i]
                    text_nospace.replace(" ", "")
                    if len(text_nospace) > 0:
                        OcrBlock.create(page=page.id, left=page_data['left'][i], top=page_data['top'][i],
                                        width=page_data['width'][i], height=page_data['height'][i],
                                        conf=page_data['conf'][i], text=page_data['text'][i])


# Usage
# ocr = OcrProcess('test')
# ocr.process_image('../test_img/conv_props.jpg')
# ocr.commit_data()


# Utility function to rescale an image while maintaining aspect ratio, is this the right place for it?
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
