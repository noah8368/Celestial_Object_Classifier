# Celestial Object Classifier

###### Madison Belk, Noah Himed

### Project Summary

The Celestial Object Classifer (COC) fetches and processes raw astrophotography
data taken by the Hubble Space Telescope, and then detects galaxies and nebulae
in the resulting images.

Data is drawn from the Hubble Legacy Archive and processed locally before
object detection is performed (with an option to fetch pre-processed data
available) by a CNN running on the STM32H743ZI board.

### Prerequistes

The `COC` software package requires the following modules:
- [astropy](https://www.astropy.org/)
- [numpy](https://numpy.org/)
- [requests](https://docs.python-requests.org/en/latest/)
- [opencv-python](https://pypi.org/project/opencv-python/)
- [scipy](https://scipy.org/)
- [torch](https://pypi.org/project/torch/)
- [torchvision](https://pypi.org/project/torchvision/)

### Image Pre-Processing

`generate_images.py` downloads raw image data from the Hubble Legacy Archive,
and performs the following steps to generate a suitable set of data to be
labelled:
1. Image stacking
2. Histogram equalization
3. Application of a bilateral filter

Image stacking is done using a module from a repo forked from Mathias Sundholm's
[image_stacking](https://github.com/maitek/image_stacking) implementation.

### Object Detection

For object detection, the [ppog's implementation of the YOLOv5-Lite](https://github.com/ppogg/YOLOv5-Lite) is used.
