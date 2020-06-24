from collections import Counter, OrderedDict
import numpy as np
import pytesseract
from pytesseract import Output


class OcrPageData:
    """Container for raw image data and detected words"""

    def __init__(self, image: np.ndarray, custom_config=''):
        """
        Gathers pytesseract data on image of a page

        Parameters
        image - image of page
        custom_config - optional custom configuration for pytesseract image_to_data function
        """
        # Retrieving text and character data
        result_data = pytesseract.image_to_data(image=image, config=custom_config, output_type=Output.DICT)
        pytesseract.image_to_data
        text_index = np.array([], dtype=int)  # index of text in original image_to_data['text'] array
        for index, text in enumerate(np.asarray(a=result_data['text']), start=0):
            if text.isalnum():
                text_index = np.append(arr=text_index, values=index)

        raw_texts = result_data['text']
        texts = np.asarray(a=raw_texts)[text_index]
        self.__text_counter = Counter(texts)  # Counts number of occurrences of each text piece
        self.__texts = np.asarray(a=list(self.text_counter.keys()))  # Unique detected texts
        chars = list(''.join(result_data['text']))
        self.__char_counter = Counter(chars)  # Counts number of occurences of each character
        self.__chars = np.asarray(a=list(self.char_counter.keys()))  # Unique number of occurrences of each character

        # Retrieving bounding box information
        self.__left = np.asarray(a=result_data['left'])[text_index]
        self.__top = np.asarray(a=result_data['top'])[text_index]
        self.__width = np.asarray(a=result_data['width'])[text_index]
        self.__height = np.asarray(a=result_data['height'])[text_index]

    @property
    def text_counter(self) -> Counter:
        """Get Counter object for detected words"""
        return self.__text_counter

    @property
    def char_counter(self) -> Counter:
        """Get Counter object for detected characters"""
        return self.__char_counter

    def char_histogram(self) -> (np.ndarray, np.ndarray):
        """Histogram of frequencies for each ASCII character"""
        frequency = OrderedDict([(ascii_value, 0) for ascii_value in np.arange(32, 127)])
        for character in list(self.char_counter.keys()):
            frequency[ord(character)] = self.char_counter[character]

        print(frequency)
        return np.asarray(a=list(frequency.values())), np.asarray(a=list(frequency.keys()))

    @property
    def texts(self) -> np.ndarray:
        """Gets list of unique text (both alpha and numerical) detected from image"""
        return self.__texts

    @property
    def chars(self) -> np.ndarray:
        """Gets list of unique characters detected from image"""
        return self.__chars

    @property
    def left(self) -> np.ndarray:
        """Gets left x-value of bounding box for each detected text"""
        return self.__left

    @property
    def top(self) -> np.ndarray:
        """Gets top y-value of bounding box for each detected text"""
        return self.__top

    @property
    def width(self) -> np.ndarray:
        """Gets width of bounding box for each detected text"""
        return self.__width

    @property
    def height(self) -> np.ndarray:
        """Gets height of each bounding box for each detected text"""
        return self.__height
