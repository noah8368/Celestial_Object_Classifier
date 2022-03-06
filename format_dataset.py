"""Reformat the dataset so that each label has a unique corresponding file and
no files exist in the dataset without a corresponding label.
"""

import os

DATASET_ROOT_DIR = os.path.join(os.curdir, "dataset")

LABEL_DIR = os.path.join(DATASET_ROOT_DIR, "labels")
DATA_DIR = os.path.join(DATASET_ROOT_DIR, "images")

subdirs = ["train", "validate", "test"]

data_Id = 0
for subdir in subdirs:
    label_subdir = os.path.join(LABEL_DIR, subdir)
    # Generate a list of all label files for the given subset of data.
    label_Ids = [int(f_name.split(".")[0]) for f_name in
                 os.listdir(label_subdir) if f_name != "classes.txt"]
    label_Ids.sort()
    label_Ids = [str(Id) for Id in label_Ids]

    data_subdir = os.path.join(DATA_DIR, subdir)
    data = os.listdir(data_subdir)
    for f_name in data:
        datum_Id = f_name.split(".")[0]
        if datum_Id not in label_Ids:
            # Remove all data that don't have a corresponding label.
            rm_datum_path = os.path.join(data_subdir, datum_Id) + ".jpeg"
            os.remove(rm_datum_path)

    for old_label_Id in label_Ids:
        # Rename each label/datum pair with a unique ID.
        old_datum_name = os.path.join(data_subdir, old_label_Id) + ".jpeg"
        new_datum_name = os.path.join(data_subdir, str(data_Id)) + ".jpeg"
        os.rename(old_datum_name, new_datum_name)

        old_label_name = os.path.join(label_subdir, old_label_Id) + ".txt"
        new_label_name = os.path.join(label_subdir, str(data_Id)) + ".txt"
        os.rename(old_label_name, new_label_name)

        data_Id += 1
