import cv2
import numpy as np
from peewee import fn
import pickle
from PIL import Image
import pytesseract
from pytesseract import Output

from db import *
from ImagePipeline import ImagePipeline
from OcrPageData import OcrPageData


# This entire file must be redone with objects
# This is just a quick demo to show how to get started with OCR
# References:
# https://nanonets.com/blog/ocr-with-tesseract/
# https://pypi.org/project/pytesseract/

# Individually crops each block of detected text against a monochromatic background
# def crop_text(image: np.ndarray, image_to_data: dict, confidence_level: int) -> np.ndarray:
#     """
#     Crops out everything except for detected words
#
#     Parameters
#     image - image for pytesseract analyze
#     image_to_data - dictionary returned by pytesseract.image_to_data function
#     confidence_level - required pytesseract confidence value threshold
#     """
#     # Error checking
#     try:
#         # Error checking for input shape
#         if type(image) != np.ndarray:
#             raise TypeError('type must be np.ndarray')
#         if len(image.shape) not in range(2, 4):
#             raise ValueError('shape of image must be 2 or 3 in dimension')
#         if len(image.shape) == 3 and len(image.shape[2]) != 3:
#             raise ValueError('RGB image must have 3 values for RGB')
#
#         # Error checking for sufficient features in image_to_dict
#         required_keys = {'left', 'top', 'width', 'height', 'conf', 'text'}
#         if not np.all(a=[key in set(image_to_data.keys()) for key in required_keys]):
#             raise ValueError('given image_to_data dict is incomplete in data')
#
#         # Error checking for valid confidence level
#         if confidence_level not in np.arange(0, 101):
#             raise ValueError('confidence level must be between 0 and 100 inclusive')
#     except (TypeError, ValueError, RuntimeError) as error:
#
#         print(str(error))
#         return
#
#     # Convert cv2-compatible image to PIL Image object first
#     image_pil = Image.fromarray(obj=image)
#     image_cropped = Image.new(mode='RGB', size=image.shape[:2][::-1], color='gray')
#
#     # Detecting words / numerals and retrieving bounding boxes
#     data = image_to_data
#     text_index = np.array([], dtype=np.int32) # Indexes to keep in original 'text' array of image_to_data
#     for index, text in enumerate(np.asarray(a=data['text']), start=0):
#         if text.isalnum() and data['conf'][index] >= confidence_level:
#             text_index = np.append(arr=text_index, values=index)
#
#     # Bounding box information
#     left = np.asarray(a=data['left'])[text_index]
#     top = np.asarray(a=data['top'])[text_index]
#     width = np.asarray(a=data['width'])[text_index]
#     height = np.asarray(a=data['height'])[text_index]
#
#     for index, item in enumerate(text_index, start=0):
#         """Crops and pastes each detected text to a gray blank background image"""
#         box = (left[index], top[index], left[index] + width[index], top[index] + height[index])
#         crop = image_pil.crop(box=box)
#         image_cropped.paste(im=crop, box=box)
#
#     return np.asarray(a=image_cropped)


# This class will process a multi page document as images and then store it in the database
class OcrProcess:
    """Processes image for each page of a document and then integrates with Sqlite database"""

    def __init__(self, name: str) -> None:
        """
        Initializes processing information

        Parameters
        name - name / title of document
        """
        self._name = name
        self._data = list()
        self.doc_id = None

    def process_image(self, image_filepath: str, oem: int, psm: int, best: bool, preprocessing: bool) -> None:
        """
        Processes image using ImagePipeline

        Parameters
        image_filepath - filepath where image is stored
        oem - OCR engine mode (0-3)
        psm - page segmentation mode (0-13)
        best - whether to use the best model (or fast model)
        preprocessing - whether to refine image temporarily with ImagePipeline before running pytesseract
        """
        # Maybe further postprocessing is needed for a better result
        # TODO: allow users to specify a custom config?
        # TODO: allow users to specify fast vs. best models
        # Custom_config = r'-l eng --psm 6 --tessdata-dir "../tessdata/best"' # lang component does not work on my machine
        # Error checking for valid config options
        try:
            if oem not in np.arange(4):
                raise ValueError('oem must be an integer between 0 and 3 inclusive')
            if psm not in np.arange(14):
                raise ValueError('psm must be an integer between 0 and 13 inclusive')
        except ValueError as error:
            print(str(error))
            return

        custom_config = f'--oem {oem} --psm {psm} --tessdata-dir ' + ('"../tessdata/best"' if best else '"../tessdata/fast"')

        # Running pipeline and collecting image metadata
        image_cv2 = cv2.imread(filename=image_filepath, flags=cv2.IMREAD_COLOR)
        image_stored_cv2 = cv2.cvtColor(src=image_cv2, code=cv2.COLOR_BGR2RGB)  # Image to be stored - cv2 / numpy array format

        # Setting up and running image processing pipeline, if necessary
        image_pipeline = ImagePipeline()
        image_pipeline.add_step(name='Grayscale', new_step=cv2.cvtColor, image_param_name='src', other_params={'code': cv2.COLOR_BGR2GRAY})
        image_pipeline.add_step(name='Binary Threshold', new_step=cv2.threshold, image_param_name='src', other_params={'thresh': 20, 'maxval': 255, 'type': cv2.THRESH_BINARY}, capture_index=1)

        # Image to be directly stored in db as RGB image in bytes;
        # bytes with no loss during compression
        image_stored_bytes = cv2.imencode(ext='.jpg', img=image_stored_cv2, params=[cv2.IMWRITE_JPEG_QUALITY, 100])[1].tostring()
        image_for_pytesseract = image_pipeline.run(image=image_cv2) if preprocessing else image_cv2
        page_data = pytesseract.image_to_data(image=image_for_pytesseract, config=custom_config, output_type=Output.DICT)  # Collects metadata on page text after refining with pipeline


        # OCRPageData object creation
        ocr_page_data = OcrPageData(image_to_data=page_data)  # Metadata on pipeline-refined image
        self._data.append((page_data, image_stored_bytes, ocr_page_data))

    def commit_data(self):
        # If the database doesn't exist yet, generate it
        create_tables()
        with db.atomic() as db_atomic:
            # Create a new entry for the document to link the pages and boxes to
            doc = OcrDocument.create(name=self._name)
            self.doc_id = doc.id
            db_atomic.commit()

            # Adding OcrPage objects to database
            for page_number, (page_data, image_file, ocr_page_data) in enumerate(self._data):
                page_count = OcrPage.select(
                    fn.Count(OcrPage.id)).scalar()  # Current number of pages in under this OcrDocument
                page_id = OcrPage.select(
                    fn.Max(OcrPage.id)).scalar() + 1 if page_count >= 1 else 0  # Uses next greatest unused id for page
                page = OcrPage.create(id=page_id, number=page_number, image=image_file, document=doc.id, ocr_page_data=pickle.dumps(obj=ocr_page_data))
                db_atomic.commit()
                for text_index, text in enumerate(page_data['text']):
                    if not text.isspace():  # Uploads non-space text pieces only
                        OcrBlock.create(page=page.id, left=page_data['left'][text_index],
                                        top=page_data['top'][text_index],
                                        width=page_data['width'][text_index], height=page_data['height'][text_index],
                                        conf=page_data['conf'][text_index], text=text)
        return self.doc_id

    @property
    def name(self) -> str:
        """Gets document name / title"""
        return self._name

    @name.setter
    def name(self, new_name: str) -> None:
        """Sets new document  name / title"""
        self._name = new_name

# Usage
# ocr = OcrProcess('test')
# ocr.process_image('../test_image/conv_props.jpg')
# ocr.commit_data()


# Utility function to rescale an image while maintaining aspect ratio, is this the right place for it?
# def resize_keep_aspect_ratio(image, width=None, height=None, inter=cv2.INTER_AREA):
#     new_dim = None
#     h, w = image.shape[:2]
#
#     if width is None and height is None:
#         return image
#     elif width is None:
#         ratio = height / h
#         new_dim = (int(w * ratio), height)
#     else:
#         ratio = width / w
#         new_dim = (width, int(h * ratio))
#
#     return cv2.resize(image, new_dim, interpolation=inter)
