
import copy
from collections import OrderedDict
import numpy as np
import PIL
from PIL import Image
from typing import Callable, NamedTuple, Union


class StepData(NamedTuple):
    """Necessary parameters for a step in the pipeline"""
    name: str
    new_step: Union[Callable, str]
    image_param_name: str
    outer_function: Callable
    other_params: dict
    capture_index: int


class ImagePipeline:
    pass


class ImagePipeline:
    """Pipeline for processing images"""

    def __init__(self):
        """Initializes empty pipeline"""
        self.pipeline = OrderedDict([])

    @property
    def pipeline(self) -> list:
        """Getter for pipeline"""
        return self.__pipeline

    @pipeline.setter
    def pipeline(self, new_pipeline: ImagePipeline) -> None:
        """Setter for pipeline"""
        self.__pipeline = copy.deepcopy(x=new_pipeline)

    def size(self) -> int:
        """Number of steps in pipeline"""
        return len(self.pipeline)

    def empty(self) -> bool:
        """Check if any steps exist in pipeline"""
        return self.size() > 0

    def clear(self) -> None:
        """Erase all steps from pipeline"""
        self.pipeline = OrderedDict([])

    def copy_steps(self, other_pipeline: ImagePipeline, start: int = 0, end: int = None) -> None:
        """
        Copies whole or part of steps from another pipeline

        Parameters
        other_pipeline - another CV2Pipeline object to copy from
        start - index of first step to be copied from other_pipeline
        end - index of immediate step after last step to be copied from other_pipeline
        """
        # Error checking
        try:
            if other_pipeline.empty():
                raise AttributeError('other_pipeline cannot be empty')
            if end > other_pipeline.size() or end == None:
                raise RuntimeError('end must be integer no greater than size of other_pipeline')
        except (AttributeError, RuntimeError) as error:
            print(str(error))
            return

        self.pipeline = OrderedDict(list(other_pipeline.pipeline.items())[start:end])

    def add_step(self, name: str, new_step: Union[Callable, str], image_param_name: str, outer_function=None,
                 other_params: dict = None, capture_index: int = 0) -> None:
        """
        Append new function to end of pipeline

        Parameters
        name - annotated name of step
        new_step - function to be added
        image_param_name - parameter name designated for image
        outer_function - earlier that new_step function is dependent on; used for PIL functions
        other_params - dictionary of other required parameters and their values besides image
        capture_index - if function returns multiple values, specify index of return tuple (default is 0 for single return)
        """
        try:
            if (outer_function == None and type(new_step) == str) or (outer_function != None and type(new_step) != str):
                raise ValueError('dependent func must be string if module is used')
        except ValueError as error:
            print(str(error))
            return

        step_tuple = StepData(name=name, new_step=new_step, image_param_name=image_param_name,
                              outer_function=outer_function,
                              other_params=other_params, capture_index=capture_index)
        self.pipeline.update({name: step_tuple})

    def run(self, image: np.ndarray, until: int = None) -> np.ndarray:
        """Run an original image through pipeline"""
        try:
            if until != None and (until < 0 or until > self.size()):
                raise IndexError('until must specify step index within pipeline')
        except IndexError as error:
            print(str(error))
            return

        # Running pipeline
        start = 0
        end = until if until != None else self.size()
        image_current = np.asarray(a=image) if type(image) == PIL.Image.Image else image
        for name, step in list(self.pipeline.items())[start:end]:
            """Run each function sequentially in pipeline"""
            print(name)
            outer_function = step.outer_function
            func = step.new_step
            image_param_name = step.image_param_name
            other_params = step.other_params

            # index of output image, in case there are multiple returned outputs
            capture_index = step.capture_index

            if outer_function == None and type(func) != str:
                """cv2 function"""
                args = {image_param_name: image_current} if other_params == None else {image_param_name: image_current,
                                                                                   **other_params}
                retval = func(**args)  # return value
                image_current = retval[capture_index] if type(retval) == tuple else retval
            else:
                """PIL function"""
                pil_object = outer_function(**{image_param_name: Image.fromarray(obj=image_current)})
                pil_func = getattr(pil_object, func)
                retval = pil_func() if other_params == None else pil_func(**other_params)
                image_current = retval[capture_index] if type(retval) == tuple else retval

            image_current = np.asarray(a=image_current) if type(image_current) == PIL.Image.Image else image_current

        return image_current

