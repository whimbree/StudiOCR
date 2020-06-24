
import cv2
import numpy as np
import pickle
import pytest

from db import create_tables, db, OcrDocument, OcrPage
from ocr import crop_text, OcrProcess
from OcrPageData import OcrPageData


@pytest.mark.db
def test_create_tables() -> None:
    """Tests the creation of tables by create_tables function"""
    create_tables()
    table_names = np.asarray(a=list(db.db.execute_sql("SELECT name FROM sqlite_master WHERE type='table'"))).flatten()
    expected_table_names = np.asarray(a=['OcrDocument', 'OcrPage'])
    print(table_names)
    assert np.all(a=[name.lower() in table_names for name in expected_table_names], axis=None)


@pytest.mark.db
def test_insert_OcrDocument() -> None:
    """Tests the insertion of data into OcrDocument table"""
    db.drop_tables(models=[OcrDocument, OcrPage], safe=True)
    create_tables()
    OcrDocument_data = [{'id': 0, 'name': 'doc_0'},
                        {'id': 1, 'name': 'doc_1'},
                        {'id': 2, 'name': 'doc_2'},
                        {'id': 3, 'name': 'doc_3'}]
    db.OcrDocument.insert_many(rows=OcrDocument_data).execute()

    # Recently inserted OcrDocument ids
    OcrDocument_id = np.asarray(a=[document.id for document in db.OcrDocument.select()])
    OcrDocument_name = np.asarray(a=[document.name for document in db.OcrDocument.select()])
    print(OcrDocument_id)
    print(OcrDocument_name)
    assert OcrDocument_id.tolist() == np.arange(4).tolist()
    assert OcrDocument_name.tolist() == [item['name'] for item in OcrDocument_data]


@pytest.mark.db
def test_insert_OcrPage():
    """Tests the insertion of data into OcrPage table"""
    db.drop_tables(models=[OcrDocument, OcrPage], safe=True)
    create_tables()

    # Creating a single OcrDocument first
    OcrDocument_data = {'id': 0, 'name': 'new_doc'}
    OcrDocument.insert(OcrDocument_data).execute()
    assert OcrDocument.select()[0].name == 'new_doc'

    # Inserting single image
    id = 0
    document = OcrDocument.get(OcrDocument.id == 0 and OcrDocument.name == 'new_doc')
    number = 1
    image_filepath = './selenium.jpg'
    image = cv2.imread(filename=image_filepath, flags=cv2.IMREAD_UNCHANGED)
    image_processed = OcrProcess.process_image(image_filepath=image_filepath)
    ocr_page_data = pickle.dumps(obj=OcrPageData(image=image))

    # OcrPage data to be inserted
    OcrPage_data = {'id': id, 'document': document, 'number': number, 'image': image, 'image_processed': image_processed, 'ocr_page_data': ocr_page_data}
    OcrPage.insert(OcrPage_data).execute()
    assert OcrDocument.select()[0].pages.count() == 1
    assert OcrPage.get().document == OcrDocument.select().where(OcrDocument.id == 0 and OcrDocument.name == 'new_doc').get()


@pytest.mark.OcrProcess
def test_OcrProcess_process_image():
    """Tests the static function process_image in OcrProcess class"""
    image_filepath = './selenium.jpg'
    OcrProcess.process_image(image_filepath=image_filepath)
    assert True


# EXTREMELY LONG TO PROCESS DUE TO SO MANY IMAGES
@pytest.mark.skip
@pytest.mark.OcrProcess
@pytest.mark.db
def test_OcrProcess_commit():
    """Tests the commit function in OcrProcess class"""
    db.drop_tables(models=[OcrDocument, OcrPage], safe=True)
    create_tables()

    image_folder_path = './aesops-fables/'
    ocr_process_object = OcrProcess(name='Aesops Fables', image_folder_path=image_folder_path)
    ocr_process_object.commit_data()

