import pickle

import numpy as np
from peewee import fn
import cv2
from PIL import Image
import pytesseract
from pytesseract import Output

from db import (db, OcrDocument, OcrPage, OcrBlock, create_tables)
from ImagePipeline import ImagePipeline
from OcrPageData import OcrPageData


class OcrEngine:
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

    def process_image(self, image_filepath: str, oem: int = 3, psm: int = 3, best: bool = True, preprocessing: bool = False) -> None:
        """
        Processes image using ImagePipeline

        Parameters
        image_filepath - filepath where image is stored
        oem - OCR engine mode (0-3)
        psm - page segmentation mode (0-13) Modes 0-2 don't perform OCR, so don't allow those
        best - whether to use the best model (or fast model)
        preprocessing - whether to refine image temporarily with ImagePipeline before running pytesseract
        """
        try:
            if oem not in range(4):
                raise ValueError(
                    'oem must be an integer between 0 and 3 inclusive')
            if psm not in range(3, 14):
                raise ValueError(
                    'psm must be an integer between 3 and 13 inclusive')
        except ValueError as error:
            print(str(error))
            return

        tessdata_best_path = '../tessdata/best'
        tessdata_fast_path = '../tessdata/fast'

        tessdata_path = tessdata_best_path if best else tessdata_fast_path

        custom_config = f'--oem {oem} --psm {psm} --tessdata-dir {tessdata_path}'

        # Running pipeline and collecting image metadata
        image_cv2 = cv2.imread(filename=image_filepath, flags=cv2.IMREAD_COLOR)
        # Image to be stored - cv2 / numpy array format
        # cv2 stores images in BGR format, but pytesseract assumes RGB format. Perform conversion.
        rgb_image_cv2 = cv2.cvtColor(src=image_cv2, code=cv2.COLOR_BGR2RGB)

        # Setting up and running image processing pipeline, if necessary
        image_pipeline = ImagePipeline()
        image_pipeline.add_step(name='Grayscale', new_step=cv2.cvtColor,
                                image_param_name='src', other_params={'code': cv2.COLOR_RGB2GRAY})
        image_pipeline.add_step(name='Binary Threshold', new_step=cv2.threshold, image_param_name='src', other_params={
                                'thresh': 20, 'maxval': 255, 'type': cv2.THRESH_BINARY}, capture_index=1)

        # Image to be directly stored in db as RGB image in bytes with no loss during compression
        # cv2.imencode is expecting BGR image, not RGB
        image_stored_bytes = cv2.imencode(ext='.jpg', img=image_cv2, params=[
                                          cv2.IMWRITE_JPEG_QUALITY, 100])[1].tostring()
        image_for_pytesseract = image_pipeline.run(
            image=rgb_image_cv2) if preprocessing else rgb_image_cv2
        # Collects metadata on page text after refining with pipeline
        page_data = pytesseract.image_to_data(
            image=image_for_pytesseract, config=custom_config, output_type=Output.DICT)

        # OCRPageData object creation
        # Metadata on pipeline-refined image
        ocr_page_data = OcrPageData(image_to_data=page_data)
        self._data.append((page_data, image_stored_bytes, ocr_page_data))

    def commit_data(self) -> int:
        # If the database doesn't exist yet, generate it
        create_tables()
        db.connect(reuse_if_open=True)
        with db.atomic():
            # Create a new entry for the document to link the pages and boxes to
            doc = OcrDocument.create(name=self._name)
            self.doc_id = doc.id

            # Adding OcrPage objects to database
            for page_number, (page_data, image_file, ocr_page_data) in enumerate(self._data):
                page = OcrPage.create(number=page_number, image=image_file,
                                      document=doc.id, ocr_page_data=pickle.dumps(obj=ocr_page_data))
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
