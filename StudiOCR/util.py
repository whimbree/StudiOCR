import os

def get_absolute_path(path):
    current_working_directory = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(current_working_directory, path)
