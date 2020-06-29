import cv2
from io import BytesIO
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import pickle
import pytesseract
from pytesseract import Output
import pytest

from db import *
from ImagePipeline import *
from ocr import *
from OcrPageData import *


@pytest.mark.db
def test_create_tables() -> None:
    """Tests the creation of tables by create_tables function"""
    create_tables()
    table_names = np.asarray(a=list(db.execute_sql("SELECT name FROM sqlite_master WHERE type='table'"))).flatten()
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
    OcrDocument.insert_many(rows=OcrDocument_data).execute()

    # Recently inserted OcrDocument ids
    OcrDocument_id = np.asarray(a=[document.id for document in OcrDocument.select()])
    OcrDocument_name = np.asarray(a=[document.name for document in OcrDocument.select()])
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
    image = cv2.imread(filename=image_filepath, flags=cv2.IMREAD_COLOR)
    image_stored = cv2.cvtColor(src=image, code=cv2.COLOR_BGR2RGB)

    # custom_config = r'-l eng --psm 6 --tessdata-dir "../tessdata/best"'
    page_data = pytesseract.image_to_data(image=image, config='', output_type=Output.DICT)
    ocr_page_data = pickle.dumps(obj=OcrPageData(image_to_data=page_data))

    # OcrPage data to be inserted
    OcrPage_data = {'id': id, 'number': number, 'image': image, 'ocr_page_data': ocr_page_data, 'document': document}
    OcrPage.insert(OcrPage_data).execute()
    assert OcrDocument.select()[0].pages.count() == 1
    assert OcrPage.get().document == OcrDocument.select().where(OcrDocument.id == 0 and OcrDocument.name == 'new_doc').get()


@pytest.mark.OcrProcess
def test_OcrProcess_process_image():
    """Tests the static function process_image in OcrProcess class"""
    image_filepath = './selenium.jpg'
    ocr_process = OcrProcess(name='name')
    ocr_process.process_image(image_filepath=image_filepath, oem=3, psm=3, best=True, preprocessing=True)
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


@pytest.mark.pytesseract
def test_pytesseract():
    """Tests pytesseract image_to_data function"""
    # custom_config = r'-l eng --psm 6 --tessdata-dir "../tessdata/best"'
    path = './selenium.jpg'
    image = cv2.imread(filename=path, flags=cv2.IMREAD_UNCHANGED)
    data = pytesseract.image_to_data(image=image, config='', output_type=Output.DICT)
    print(data)
    print(list(data.keys()))
    print(set(data.keys()))

@pytest.mark.pipeline
def test_pipeline_init():
    """Test for any problems with initializing ImagePipeline"""
    try:
        image_pipeline = ImagePipeline()
    except RuntimeError as error:
        print(str(error))
        assert False
    assert True

@pytest.mark.pipeline
def test_pipeline_cv2():
    """Tests ImagePipeline on cv2 functions only"""
    image_filepath = './selenium.jpg'
    image = cv2.imread(filename=image_filepath, flags=cv2.IMREAD_COLOR)

    # Running pipeline to refine image
    image_pipeline = ImagePipeline()
    image_pipeline.add_step(name='Grayscale', new_step=cv2.cvtColor, image_param_name='src', other_params={'code': cv2.COLOR_BGR2GRAY})
    image_pipeline.add_step(name='Binary Threshold', new_step=cv2.threshold, image_param_name='src', other_params={'thresh': 20, 'maxval': 255, 'type': cv2.THRESH_BINARY}, capture_index=1)
    image_pipeline.add_step(name='Median Blur', new_step=cv2.medianBlur, image_param_name='src', other_params={'ksize': 7})
    image_pipeline.add_step(name='Rotate 90 COUNTERCLOCKWISE', new_step=cv2.rotate, image_param_name='src', other_params={'rotateCode': cv2.ROTATE_90_COUNTERCLOCKWISE})
    image_piped = image_pipeline.run(image=image)

    fig = plt.figure(num=None, figsize=(40, 10), edgecolor=None, facecolor=None)
    plt.subplot(121)
    plt.title(label='Original pipeline_cv2', size=24)
    plt.imshow(X=image, aspect='auto', origin='upper')

    plt.subplot(122)
    plt.title(label='Piped pipeline_cv2', size=24)
    plt.imshow(X=image_piped, aspect='auto', origin='upper')


def test_image_bytes_to_cv2_np():
    """Tests conversion of image from bytes to cv2"""
    image_filepath = './selenium.jpg'
    image_file = open(file=image_filepath, mode='rb')

    image_bytes = image_file.read()  # bytes
    image_cv2 = cv2.imdecode(buf=np.frombuffer(buffer=image_bytes, dtype=np.uint8), flags=cv2.IMREAD_UNCHANGED)[:, :, :3]  # np.ndarray
    print(f'image_np:\n{type(image_cv2)}\n{image_cv2.shape}\n{image_cv2}\n')

    # Saving
    cv2.imwrite(filename='./test_bytes_to_cv2_np.jpg', img=image_cv2)

    # Plotting
    plt.title(label='image_cv2', size=24)
    plt.imshow(X=image_cv2, aspect='auto', origin='upper')
    plt.show()

@pytest.mark.skip
def test_image_bytes_to_PIL():
    """Tests conversion of image from bytes to PIL"""
    image_filepath = './selenium.jpg'
    image_file = open(file=image_filepath, mode='rb')

    temp = Image.open(fp=image_filepath)
    width, height = temp.size
    image_pil = Image.frombytes(mode='RGB', size=(width, height), data=BytesIO(initial_bytes=image_file.read()).getvalue())
    print(f'image_pil:\n{type(image_pil)}\n{image_pil}\n')

    # Saving
    image_pil.save(fp='./test_bytes_to_pil.jpg', format='JPEG')
    image_pil.show(title='image_pil')

    # Plotting
    plt.title(label='image_pil', size=24)
    plt.imshow(X=np.asarray(a=image_pil), aspect='auto', origin='upper')
    plt.show()

def test_image_np_to_bytes():
    """Tests preprocessing of image from bytes to cv2"""
    image_filepath = './selenium.jpg'
    image_file = open(file=image_filepath, mode='rb')
    print(f'image_file:\n{type(image_file)}\n{image_file}\n')
    temp = image_file.read()
    print(type(temp))
    # print(temp)

    # convert to bytes
    image_cv2 = cv2.imread(filename=image_filepath, flags=cv2.IMREAD_COLOR)
    image_bytes = cv2.imencode(ext='.jpg', img=image_cv2, params=None)[1].tostring()
    f = open(file='./test_np_to_bytes.jpg', mode='wb')
    f.write(image_bytes)
    print(type(image_bytes))
