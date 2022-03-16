"""Generate the training dataset for object segmentation.

Fetch images from the Hubble Legacy Archive, and divide them into three
sets: training, validation, and testing.
"""

import glob
import math
import os
import random
import shutil

from astro_img_handling import gen_img_set, IMG_EXT


def create_datasets(processing_manually=False, num_imgs=50,
                    train_portion=0.7, validation_portion=0.2,
                    test_portion=0.1):
    """Collects and divides data from the Hubble Legacy Archive for labelling.

    Args:
        processing_manually: A bool value indicating whether custom processing
                             on randomly selected images should be used.
        train_portion: Portion of data to use to train model.
        validation_portion: Portion of data to use to tune hyperparameters.
        test_portion: Portion of data to use to test the model.
    """

    if round(train_portion + validation_portion + test_portion) != 1:
        print("ERROR: data subset proportions must add to 1 (100%).")
        return

    img_path = os.path.join(os.curdir, "images")
    # Delete the folder "./images" if it exists to avoid mixing
    # datasets and non-image files into the current set of data.
    if os.path.exists(img_path):
        shutil.rmtree(img_path)
    os.mkdir(img_path)

    # Fetch data from the Hubble Legacy Archive.
    gen_img_set(img_path, process_manually=processing_manually,
                num_img=num_imgs)
    imgs = glob.glob(os.path.join(img_path, "*%s" % IMG_EXT))
    random.shuffle(imgs)
    num_samples = len(imgs)

    # Create a training data subset.
    num_train = math.floor(train_portion * num_samples)
    training_imgs = imgs[:num_train]
    training_img_path = os.path.join(img_path, "training_dataset")
    os.mkdir(training_img_path)
    for img, img_idx in zip(training_imgs, range(num_train)):
        shutil.move(img, os.path.join(training_img_path,
                                      str(img_idx) + IMG_EXT))

    # Create a validation data subset.
    num_val = math.floor(validation_portion * num_samples)
    validation_imgs = imgs[num_train:num_train + num_val]
    validation_img_path = os.path.join(img_path, "validation_dataset")
    os.mkdir(validation_img_path)
    for img, img_idx in zip(validation_imgs, range(num_val)):
        shutil.move(img, os.path.join(validation_img_path,
                                      str(img_idx) + IMG_EXT))

    # Create a testing data subset.
    num_test = math.ceil(test_portion * num_samples)
    testing_imgs = imgs[-num_test:]
    test_img_path = os.path.join(img_path, "testing_dataset")
    os.mkdir(test_img_path)
    for img, img_idx in zip(testing_imgs, range(num_test)):
        shutil.move(img, os.path.join(test_img_path, str(img_idx) + IMG_EXT))


if __name__ == "__main__":
    create_datasets(processing_manually=True)
