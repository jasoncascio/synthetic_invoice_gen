import os
import zipfile
from abc import ABC, abstractmethod

class BaseExporter(ABC):
    @abstractmethod
    def __enter__(self):
        pass

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @abstractmethod
    def write(self, filename: str, data: bytes) -> None:
        pass

class LocalFileExporter(BaseExporter):
    """ Spawns 1 JSON file individually into an output directory. """
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def write(self, filename: str, data: bytes) -> None:
        path = os.path.join(self.output_dir, filename)
        with open(path, 'wb') as f:
            f.write(data)

class SingleFileBytesExporter(BaseExporter):
    """ Append streams for writing gigantic 10GB JSON Line or JSON Array aggregates seamlessly """
    def __init__(self, output_path: str):
        self.output_path = output_path
        self.file_handle = None

    def __enter__(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.output_path)), exist_ok=True)
        self.file_handle = open(self.output_path, 'wb')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.file_handle:
            self.file_handle.close()

    def write(self, filename: str, data: bytes) -> None:
        if self.file_handle:
            self.file_handle.write(data)
