import os
import sys


def get_absolute_path(path) -> str:
    current_working_directory = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(current_working_directory, path)


# https://oxavelar.wordpress.com/2011/03/09/how-to-get-the-number-of-available-threads-in-python/
def get_threads() -> int:
    """ Returns the number of available threads on a posix/win based system """
    if sys.platform == 'win32':
        return (int)(os.environ['NUMBER_OF_PROCESSORS'])
    else:
        return (int)(os.popen('grep -c cores /proc/cpuinfo').read())
