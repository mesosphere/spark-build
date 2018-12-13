import os.path
import sys

this_file_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.normpath(os.path.join(this_file_dir, '..', '..', 'tests')))
sys.path.append(os.path.normpath(os.path.join(this_file_dir, '..', '..', 'testing')))
sys.path.append(os.path.normpath(os.path.join(this_file_dir, '..', '..', 'spark-testing')))
