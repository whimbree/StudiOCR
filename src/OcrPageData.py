
from collections import Counter, OrderedDict
import numpy as np
import pytesseract
from pytesseract import Output


class OcrPageData:
    """Container for raw image data and detected words"""

    def __init__(self, image_to_data: dict) -> None:
        """
        Gathers pytesseract data on image of a page

        Parameters
        image - image of page
        custom_config - optional custom configuration for pytesseract image_to_data function
        """
        # Error checking for sufficient features in image_to_dict
        try:
            required_keys = {'left', 'top', 'width', 'height', 'conf', 'text'}
            if not np.all(a=[key in set(image_to_data.keys()) for key in required_keys]):
                raise ValueError(
                    'given image_to_data dict is incomplete in data')
        except ValueError as error:
            print(str(error))
            return

        result_data = image_to_data
        # index of text in original image_to_data['text'] array
        text_index = np.array([], dtype=int)
        for index, text in enumerate(np.asarray(a=result_data['text']), start=0):
            if not text.isspace():
                text_index = np.append(arr=text_index, values=index)

        raw_texts = result_data['text']
        texts = np.asarray(a=raw_texts)[text_index]
        # Counts number of occurrences of each text piece
        self.__text_counter = Counter(texts)
        # Unique detected texts, sorted alphabetically
        self.__texts = np.asarray(a=sorted(list(self.text_counter.keys())))
        chars = list(''.join(result_data['text']))
        # Counts number of occurences of each character
        self.__char_counter = Counter(chars)
        # Unique number of occurrences of each character, sorted alphabetically
        self.__chars = np.asarray(a=sorted(list(self.char_counter.keys())))

        # Retrieving text bounding box information
        self.__left = np.asarray(a=result_data['left'])[text_index]
        self.__top = np.asarray(a=result_data['top'])[text_index]
        self.__width = np.asarray(a=result_data['width'])[text_index]
        self.__height = np.asarray(a=result_data['height'])[text_index]

        # Retrieving confidence level information as a dict of sets of conf values for a unique text
        raw_confidence_levels = result_data['conf']
        confidence_levels = np.asarray(a=raw_confidence_levels)[
            text_index]  # Corresponds to kept texts
        self.__confidence_level = dict()
        for text, conf in zip(texts, confidence_levels):
            if text in self.__confidence_level:  # Check if text is already added
                self.__confidence_level[text].add(conf)
            else:
                self.__confidence_level.update({text: {conf}})

    @property
    def char_counter(self) -> Counter:
        """Get Counter object for detected characters"""
        return self.__char_counter

    @property
    def chars(self) -> np.ndarray:
        """Gets list of unique characters detected from image"""
        return self.__chars

    @property
    def confidence_level(self) -> dict:
        """Gets a dict of confidence levels for each unique text"""
        return self.__confidence_level

    @property
    def text_counter(self) -> Counter:
        """Get Counter object for detected words"""
        return self.__text_counter

    def char_histogram(self) -> (np.ndarray, np.ndarray):
        """Histogram of frequencies for each ASCII character"""
        frequency = OrderedDict([(ascii_value, 0)
                                 for ascii_value in np.arange(32, 127)])
        for character in list(self.char_counter.keys()):
            frequency[ord(character)] = self.char_counter[character]

        return np.asarray(a=list(frequency.values())), np.asarray(a=list(frequency.keys()))

    @property
    def texts(self) -> np.ndarray:
        """Gets list of unique text (both alpha and numerical) detected from image"""
        return self.__texts

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
