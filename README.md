# Celestial Object Classifier

###### Noah Himed, Madison Belk

### Project Summary

This project consists of two parts: a pipeline to automate image processing
of astronomy photos, and a deep learning system to detect galaxies and nebulae
in processed data. The latter system will use the [YOLO](https://arxiv.org/abs/1506.02640) object detection
algorithm.

### Prerequistes

This software package requires `astropy`, `numpy` and `scipy`. These can be
installed using [pip](https://pip.pypa.io/en/stable/) as follows:
```
pip install requests
pip install git+git://github.com/dfm/casjobs@master
pip install git+git://github.com/rlwastro/mastcasjobs@master
pip install fastkde
```