
import cv2
import numpy as np
<<<<<<< Updated upstream
import os
from peewee import fn
import pickle
import PIL
from PIL import Image, ImageEnhance
import pytesseract
from pytesseract import Output

from db import create_tables, db, OcrDocument, OcrPage
from ImagePipeline import ImagePipeline
from OcrPageData import OcrPageData
=======
import pickle
from PIL import Image
import pytesseract
from pytesseract import Output

from db import *
from ImagePipeline import ImagePipeline
from OCRPageData import OcrPageData
>>>>>>> Stashed changes

# This entire file must be redone with objects
# This is just a quick demo to show how to get started with OCR
# References:
# https://nanonets.com/blog/ocr-with-tesseract/
# https://pypi.org/project/pytesseract/

# Individually crops each block of detected text against a monochromatic background
def crop_text(image: np.ndarray) -> np.ndarray:
    """Crops out everything except for detected words"""
    # Error checking for input shape
    try:
        if type(image) != np.ndarray:
            raise TypeError('type must be np.ndarray')
        if len(image.shape) not in range(2, 4):
            raise ValueError('shape of image must be 2 or 3 in dimension')
        if len(image.shape) == 3 and len(image.shape[2]) != 3:
            raise ValueError('RGB image must have 3 values for RGB')
    except (TypeError, ValueError, RuntimeError) as error:
        print(str(error))
        return

    # Convert cv2-compatible image to PIL Image object first
    image_pil = Image.fromarray(obj=image)
    image_cropped = Image.new(mode='RGB', size=image.shape[:2][::-1], color='gray')

    # Detecting words / numerals and retrieving bounding boxes
    data = pytesseract.image_to_data(image=image, lang=None, config='', nice=0, output_type=Output.DICT)
    text_index = np.array([], dtype=np.int32)
    for index, text in enumerate(np.asarray(a=data.get('text')), start=0):
        if text.isalnum():
            text_index = np.append(arr=text_index, values=index)

    # Bounding box information
    left = np.asarray(a=data['left'])[text_index]
    top = np.asarray(a=data['top'])[text_index]
    width = np.asarray(a=data['width'])[text_index]
    height = np.asarray(a=data['height'])[text_index]

    for index, item in enumerate(text_index, start=0):
        """Crops and pastes each detected text to a gray blank background image"""
        box = (left[index], top[index], left[index] + width[index], top[index] + height[index])
        crop = image_pil.crop(box=box)
        image_cropped.paste(im=crop, box=box)

    return np.asarray(a=image_cropped)
<<<<<<< Updated upstream
=======

>>>>>>> Stashed changes

# This class will process a multi page document as images and then store it in the database
class OcrProcess:
    """Processes image for each page of a document and then integrates with Sqlite database"""
    custom_config = r'-l eng --psm 6 --tessdata-dir "../tessdata/best"'

    def __init__(self, name: str, image_folder_path: str) -> None:
        """
        Processes new document by storing the document and individual page images
        name - name / title of document
        image_folder_path - directory path of folder holding images of each page in document; must end in '/'
        """
        self.__name = name
        self.__image_folder_path = image_folder_path

    @staticmethod
    def process_image(image_filepath: str) -> np.ndarray:
        # Maybe further postprocessing is needed for a better result
        # TODO: allow users to specify a custom config?
        # TODO: allow users to specify fast vs. best models
<<<<<<< Updated upstream
        image = cv2.imread(filename=image_filepath, flags=cv2.IMREAD_UNCHANGED)

        # Setting up and running image processing pipeline
        image_pipeline = ImagePipeline()

        # Convert to RGB colorspace for Tesseract OCR
        # image_pipeline.add_step(name='Color Convert', new_step=cv2.cvtColor, image_param_name=, other_params={'code': cv2.COLOR_BGR2RGB})
        image_pipeline.add_step(name='Grayscale', new_step=cv2.cvtColor, image_param_name='src', other_params={'code': cv2.COLOR_BGR2GRAY})
        image_pipeline.add_step(name='Contrast', outer_function=PIL.ImageEnhance.Contrast, new_step='enhance', image_param_name='image', other_params={'factor': 4})
        image_pipeline.add_step(name='Sharpness', outer_function=PIL.ImageEnhance.Contrast, new_step='enhance', image_param_name='image', other_params={'factor': 4})
        image_pipeline.add_step(name='Crop', new_step=crop_text, image_param_name='image')

        image_processed = image_pipeline.run(image=image)
        return image_processed
=======
        custom_config = r'-l eng --psm 6 --tessdata-dir "../tessdata/best"'

        image = cv2.imread(image_filepath)
        # Convert to RGB colorspace for Tesseract OCR
        page_data = pytesseract.image_to_data(image, config=custom_config, output_type=Output.DICT)
        image_file = open(image_filepath, 'rb')

        # Building and running image processing pipeline
        image_pipeline = ImagePipeline()
        image_pipeline.add_step(name='BGR to RGB', new_step=cv2.cvtColor, image_param_name='src',
                                other_params={'code': cv2.COLOR_BGR2RGB})
        image_pipeline.add_step(name='Crop', new_step=crop_text, image_param_name='image')

        image_str = image_file.read()  # bytes
        image_arr = np.fromstring(string=image_str.decode(encoding='utf-8'), dtype=np.uint8)  # np.ndarray
        image_np = cv2.imdecode(buf=image_arr, flags=cv2.IMREAD_UNCHANGED)  # np.ndarray form
        image_cropped = image_pipeline.run(image=image_np)  # np.ndarray form
        image_cropped_bytes = image_cropped.tobytes(order='C')

        # OCRPageData object creation
        ocr_page_data = OcrPageData(image=image_np, custom_config=custom_config)

        self._data.append((page_data, image_cropped_bytes, ocr_page_data))
>>>>>>> Stashed changes

    def commit_data(self):
        # If the database doesn't exist yet, generate it
        create_tables()
        with db.atomic() as db_atomic:
            # Create a new entry for the document to link the pages and boxes to
<<<<<<< Updated upstream
            document_count = OcrDocument.select(fn.Count(OcrDocument.id)).scalar()
            document_id = OcrDocument.select(fn.Max(OcrDocument.id)).scalar() + 1 if document_count >= 1 else 0 # Uses next greatest unused id for document
            print(document_id)
            print(type(document_id))
            doc = OcrDocument.create(id=document_id, name=self.__name)
            db_atomic.commit()

            # Adding OcrPage objects to database
            image_names = np.asarray(a=sorted([file for file in os.listdir(path=self.__image_folder_path) if file.endswith('.jpg')]))
            for i, image_name in enumerate(image_names, start=1):
=======
            doc = OcrDocument.create(name=self._name)
            self.doc_id = doc.id
            for i, (page_data, image_file, ocr_page_data) in enumerate(self._data):
                page = OcrPage.create(number=i, image=image_file, document=doc.id, ocr_page_data=pickle.dumps(obj=ocr_page_data))
                for i in range(len(page_data)):
                    text_nospace = page_data['text'][i]
                    text_nospace.replace(" ", "")
                    if len(text_nospace) > 0:
                        OcrBlock.create(page=page.id, left=page_data['left'][i], top=page_data['top'][i],
                                        width=page_data['width'][i], height=page_data['height'][i],
                                        conf=page_data['conf'][i], text=page_data['text'][i])
        return self.doc_id
>>>>>>> Stashed changes

                # Creating objects for table fields
                page_count = OcrPage.select(fn.Count(OcrPage.id)).scalar()
                id = OcrPage.select(fn.Max(OcrPage.id)).scalar() + 1 if page_count >= 1 else 0 # Uses next greatest unused id for page
                image_filepath = self.__image_folder_path + image_name
                image = cv2.imread(filename=image_filepath, flags=cv2.IMREAD_UNCHANGED)
                image_processed = OcrProcess.process_image(image_filepath=image_filepath)
                ocr_page_data = pickle.dumps(obj=OcrPageData(image=image_processed)) # Serializes page image metadata to 'bytes' type
                OcrPage.create(id=id, number=i, document=doc, image=image, image_processed=image_processed, ocr_page_data=ocr_page_data)
                db_atomic.commit()

    @property
    def name(self) -> str:
        """Gets document name / title"""
        return self.__name

    @name.setter
    def name(self, new_name: str) -> None:
        """Sets new document  name / title"""
        self.__name = new_name

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

