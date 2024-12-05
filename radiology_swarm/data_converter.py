import numpy as np
import pydicom
from PIL import Image
import nibabel as nib
from pathlib import Path
import logging
from typing import Optional, Union, Tuple


class MedicalImageConverter:
    """
    A utility class for converting various medical image formats to JPEG
    while preserving image quality and relevant metadata.

    Supports:
    - DICOM (.dcm)
    - NIfTI (.nii, .nii.gz)
    - MINC (.mnc)
    - NRRD (.nrrd)
    - Common formats (.png, .tiff)
    """

    def __init__(self, output_dir: str = "converted_images"):
        """Initialize the converter with output directory."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger(__name__)

    def _normalize_image(self, image: np.ndarray) -> np.ndarray:
        """Normalize image to 8-bit format."""
        if image.dtype != np.uint8:
            image = image.astype(float)
            image = (
                (image - image.min())
                / (image.max() - image.min())
                * 255
            ).astype(np.uint8)
        return image

    def _adjust_contrast(
        self,
        image: np.ndarray,
        window_center: Optional[float] = None,
        window_width: Optional[float] = None,
    ) -> np.ndarray:
        """Apply windowing/contrast adjustment for medical images."""
        if window_center is None or window_width is None:
            return image

        min_value = window_center - window_width // 2
        max_value = window_center + window_width // 2
        image = np.clip(image, min_value, max_value)
        return self._normalize_image(image)

    def _read_dicom(self, file_path: str) -> Tuple[np.ndarray, dict]:
        """Read DICOM file and extract image with metadata."""
        try:
            dcm = pydicom.dcmread(file_path)

            # Extract important metadata
            metadata = {
                "PatientID": getattr(dcm, "PatientID", "Unknown"),
                "StudyDate": getattr(dcm, "StudyDate", "Unknown"),
                "Modality": getattr(dcm, "Modality", "Unknown"),
                "WindowCenter": getattr(dcm, "WindowCenter", None),
                "WindowWidth": getattr(dcm, "WindowWidth", None),
            }

            # Convert pixel data to numpy array
            if hasattr(dcm, "pixel_array"):
                image = dcm.pixel_array
            else:
                raise ValueError("DICOM file contains no image data")

            return image, metadata

        except Exception as e:
            self.logger.error(f"Error reading DICOM file: {str(e)}")
            raise

    def convert_to_jpeg(
        self,
        input_path: Union[str, Path],
        output_filename: Optional[str] = None,
        quality: int = 95,
    ) -> str:
        """
        Convert medical image to JPEG format.

        Args:
            input_path: Path to input image file
            output_filename: Custom filename for output (optional)
            quality: JPEG quality (0-100)

        Returns:
            Path to converted JPEG file
        """
        input_path = Path(input_path)

        if not input_path.exists():
            raise FileNotFoundError(
                f"Input file not found: {input_path}"
            )

        # Generate output filename if not provided
        if output_filename is None:
            output_filename = f"{input_path.stem}_converted.jpg"

        output_path = self.output_dir / output_filename

        try:
            # Handle different file formats
            if input_path.suffix.lower() == ".dcm":
                image, metadata = self._read_dicom(str(input_path))
                image = self._adjust_contrast(
                    image,
                    metadata.get("WindowCenter"),
                    metadata.get("WindowWidth"),
                )

            elif input_path.suffix.lower() in [".nii", ".gz"]:
                nii_img = nib.load(str(input_path))
                image = self._normalize_image(nii_img.get_fdata())

            elif input_path.suffix.lower() in [
                ".png",
                ".jpg",
                ".jpeg",
                ".tiff",
                ".tif",
            ]:
                image = np.array(Image.open(input_path))

            else:
                raise ValueError(
                    f"Unsupported file format: {input_path.suffix}"
                )

            # Ensure proper image orientation
            if len(image.shape) > 2:
                if image.shape[2] == 3 or image.shape[2] == 4:
                    pass  # Keep RGB/RGBA as is
                else:
                    image = image[
                        :, :, 0
                    ]  # Take first slice of 3D volume

            # Save as JPEG
            Image.fromarray(image).save(
                output_path, "JPEG", quality=quality, optimize=True
            )

            self.logger.info(
                f"Successfully converted {input_path} to JPEG: {output_path}"
            )
            return str(output_path)

        except Exception as e:
            self.logger.error(
                f"Error converting {input_path}: {str(e)}"
            )
            raise

    def batch_convert(
        self, input_dir: Union[str, Path], file_pattern: str = "*.*"
    ) -> list:
        """
        Batch convert all supported medical images in a directory.

        Args:
            input_dir: Directory containing medical images
            file_pattern: Glob pattern for file selection

        Returns:
            List of paths to converted files
        """
        input_dir = Path(input_dir)
        converted_files = []

        for file_path in input_dir.glob(file_pattern):
            try:
                if file_path.suffix.lower() in [
                    ".dcm",
                    ".nii",
                    ".gz",
                    ".png",
                    ".tiff",
                    ".tif",
                ]:
                    converted_path = self.convert_to_jpeg(file_path)
                    converted_files.append(converted_path)
            except Exception as e:
                self.logger.error(
                    f"Error converting {file_path}: {str(e)}"
                )
                continue

        return converted_files


# Example usage
if __name__ == "__main__":
    converter = MedicalImageConverter(output_dir="converted_images")

    # Single file conversion
    jpeg_path = converter.convert_to_jpeg("example.dcm")

    # Batch conversion
    converted_files = converter.batch_convert(
        "input_directory", "*.dcm"
    )
