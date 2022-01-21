# Celestial Object Classifier

###### Madison Belk, Noah Himed

### Project Summary

This project consists of two parts: a pipeline to automate image processing
of astronomy photos, and a deep learning system to detect galaxies and nebulae
in processed data. The latter system will use the [YOLO](https://arxiv.org/abs/1506.02640) object detection
algorithm.

### Prerequistes

The `COC` software package requires the following modules:
- [astropy](https://www.astropy.org/)
- [numpy](https://numpy.org/)
- [requests](https://docs.python-requests.org/en/latest/)

### Image Pre-Processing

`generate_images.py` downloads raw image data from the Hubble Legacy Archive,
and performs the following steps to generate a suitable set of data to be
labelled:
1. Image stacking
2. Histogram equalization
3. Application of a bilateral filter

Image stacking is done using a module from a repo forked from Mathias Sundholm's
[image_stacking](https://github.com/maitek/image_stacking) implementation.