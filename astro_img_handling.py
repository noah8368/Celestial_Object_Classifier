'''Download and process raw image data from the Hubble Legacy Archive

Define routines to collect raw image data from the HLA, perform image stacking,
and further filtering.
'''

import cv2 as cv
import glob
import numpy as np
import os
import requests
import shutil

from astropy.table import Table
from custom_exceptions import EmptySearch, NotEnoughExposures
from image_stacking.auto_stack import stackImagesECC
from socket import timeout
from urllib.error import URLError

IMG_EXT = ".jpeg"


def gen_img_set(img_path, process_manually=False, num_img=50):
    """Downloads an processed image for each galaxy and nebula location.

    Probes the Hubble Legacy Archive for images of galaxies and nebulae.

    Args:
        img_path: Location to locally save image path.
        coord_fs: Tuples of paths to a text file with celestial coordinates of
                  Celestial Objects of Interest.
        process_manually: If true, download exposures from the Hubble
                          Legacy Archive and manually process them rather
                          than pre-processed data.
        num_img: Number of images to generate through manual processing.
    """

    def remove_exposures():
        """Removes exposures from an in-progress image compilation."""
        exposure_files = glob.glob(os.path.join(img_path,
                                                "exposure_*" + IMG_EXT))
        for file in exposure_files:
            os.remove(file)

    def generate_rand_loc():
        ra = round(np.random.uniform(0, 360), 3)
        dec = round(np.rad2deg(np.arcsin(np.random.uniform(-1, 1))), 3)
        return ra, dec

    if process_manually:
        # Randomly sample num_img celestial coordinates to pull images of, and
        # manually process those images locally.
        prev_locs = []
        for img_idx in range(num_img):
            ra, dec = generate_rand_loc()

            while True:
                if (ra, dec) in prev_locs:
                    # Generate a new location if the current location has
                    # already been searched.
                    ra, dec = generate_rand_loc()
                    continue

                try:
                    __fetch_img(ra, dec, img_path, processing_manually=True)
                except (cv.error, EmptySearch, NotEnoughExposures):
                    # Generate a new location if the search returns
                    # exposures that result in an unrecoverable error.
                    remove_exposures()
                    ra, dec = generate_rand_loc()
                    continue
                except (ConnectionError, URLError, timeout,
                        requests.exceptions.ConnectionError):
                    # Retry the same coordinate pair if the connection fails.
                    continue

                prev_locs.append((ra, dec))
                break
    else:
        # Download all high quality images in the Hubble Legacy Archive.
        __all_sky_search("HLSP", img_path)


def __all_sky_search(img_type, data_path):
    """Downloads an image for each location returned from an all-sky search.

    Args:
        img_type: Type of image to retrieve. Options are "best",
                  "exposure", "combined", "mosaic", "color", "HLSP",
                  and "all".
    """
    all_sky_img_table = __query_hubble_legacy_archive(ra=0, dec=0, radius=180,
                                                      data_product=img_type,
                                                      inst="WFC3")

    # Group photos by right ascension and declination.
    grouped_img_urls = {}
    for entry in all_sky_img_table:
        img_coords = (entry["RA"], entry["DEC"])
        if img_coords in grouped_img_urls:
            grouped_img_urls[img_coords].append(entry["URL"])
        else:
            grouped_img_urls[img_coords] = [entry["URL"]]

    num_imgs = len(grouped_img_urls)
    for img_urls, img_idx in zip(grouped_img_urls.values(), range(num_imgs)):
        # Save the first image for each coordinate.
        img_url = img_urls[0]
        img_path = os.path.join(data_path, "%d%s" % (img_idx, IMG_EXT))
        print("Saving image %s of %s..." % (img_idx + 1, num_imgs))
        while True:
            try:
                __save_img(img_url, img_path)
            except (ConnectionError, URLError, timeout,
                    requests.exceptions.ConnectionError):
                # Retry the same download if the connection fails.
                continue
            break


def __fetch_img(ra, dec, data_path, processing_manually):
    """Downloads a processed image from the Hubble Legacy Archive at (ra, dec).

    Args:
        ra, dec: Right ascension and declination. Central position in deg
                    for the cutout.
        data_path: Location to locally save image.
        processing_manually: Boolean value to indicate if custom processing
                             needs to be done.
    """

    SEARCH_RADIUS = 0.4
    MIN_NUM_EXPOSURES = 5
    try:
        if processing_manually:
            img_table = __query_hubble_legacy_archive(ra, dec, SEARCH_RADIUS,
                                                      "exposure", "WFC3")
        else:
            img_table = __query_hubble_legacy_archive(ra, dec, SEARCH_RADIUS,
                                                      "HLSP", "WFC3")
        if len(img_table) == 0:
            raise EmptySearch
    except ValueError:
        print("ERROR: Invalid query options")

    # Group photos by right ascension and declination.
    grouped_img_urls = {}
    for entry in img_table:
        exposure_loc = (entry["RA"], entry["DEC"])
        if exposure_loc in grouped_img_urls:
            grouped_img_urls[exposure_loc].append(entry["URL"])
        else:
            grouped_img_urls[exposure_loc] = [entry["URL"]]

    if processing_manually:
        # Select the location with the most exposures for stacking.
        loc_index = np.argmax([len(url_list) for url_list in
                               list(grouped_img_urls.values())])
        exposure_urls = list(grouped_img_urls.values())[loc_index]
        if len(exposure_urls) < MIN_NUM_EXPOSURES:
            raise NotEnoughExposures

        print("\nProcessing data for coordinates RA:", str(ra) + "° DEC:",
              str(dec) + "°\n")

        # Download exposures for each position.
        exposure_count = 0
        exposure_path_list = []
        for exposure_url in exposure_urls:
            exposure_count += 1
            exposure_path = os.path.join(data_path,
                                         "exposure_" + str(exposure_count)
                                         + IMG_EXT)
            exposure_path_list.append(exposure_path)
            __save_img(exposure_url, exposure_path)

        # Combine exposures for the chosen location into a single image.
        combined_img = stackImagesECC(exposure_path_list)
        ra, dec = list(grouped_img_urls.keys())[loc_index]
        img_path = os.path.join(data_path, "RA_" + str(ra) + "__DEC_"
                                + str(dec) + IMG_EXT)

        # Remove downloaded exposures once they've been combined.
        for exposure_f in exposure_path_list:
            os.remove(exposure_f)

        filtered_img = cv.bilateralFilter(combined_img, 5, 75, 75)
        filtered_img = __enhance_contrast(filtered_img)
        cv.imwrite(img_path, filtered_img)
    else:
        print("\nSaving image for coordinates RA:", str(ra) + "° DEC:",
              str(dec) + "°\n")
        # Save the first image of the first location from the query.
        ra, dec = list(grouped_img_urls.keys())[0]
        img_url = list(grouped_img_urls.values())[0][0]
        img_path = os.path.join(data_path, "RA_" + str(ra) + "__DEC_"
                                + str(dec) + IMG_EXT)
        __save_img(img_url, img_path)


def __enhance_contrast(img_matrix, bins=256):
    """Applies histogram equalization to improve image contrast.

    Args:
        TODO(Madison): Summarize these params.
        bins: ?
        img_matrix: ?
    """
    img_flattened = img_matrix.flatten()
    img_hist = np.zeros(bins)

    # Compute the frequency count of each pixel.
    for pix in img_matrix:
        img_hist[pix] += 1

    # Normalize the histogram.
    cum_sum = np.cumsum(img_hist)
    norm = (cum_sum - cum_sum.min()) * 255
    n_ = cum_sum.max() - cum_sum.min()
    uniform_norm = norm / n_
    uniform_norm = uniform_norm.astype('int')

    img_eq = uniform_norm[img_flattened]
    # Reshape the flattened matrix to its original shape.
    img_eq = np.reshape(a=img_eq, newshape=img_matrix.shape)

    return img_eq


def __save_img(url, path):
    """Downloads the image from a given url.

    Args:
        url: Location to download image from.
        path: Location to save image to locally.
    """
    req = requests.get(url, stream=True)
    OK_STATUS = 200
    # Ensure the HTTPS reply's status code indicates success (OK status).
    if req.status_code == OK_STATUS:
        req.raw.decode_content = True
    else:
        raise ConnectionError()
    img_file = open(path, "wb")
    shutil.copyfileobj(req.raw, img_file)
    img_file.close()


def __query_hubble_legacy_archive(ra, dec, radius, data_product,
                                  inst, spectral_elements=(),
                                  autoscale=99.5, asinh=1):
    """Queries image data from the Hubble Legacy Archive.

    Args:
        ra, dec: Right ascension and declination. Central position in deg
                    for the cutout.
        radius: Radius of the cutout, in degrees.
        data_product: Type of image to retrieve. Options are "best",
                        "exposure", "combined", "mosaic", "color", "HLSP",
                        and "all".
        inst: Instrument to collect data from on Hubble Space Telescope
        format: Queried data file formats.
        spectral elements: A tuple of strings of filter color identifiers.
        autoscale: Percentage of image histogram to retain.
        asinh: If nonzero value, use Lupton asinh contrast algorithm.
        format: Image file format.

    Returns:
        An astropy Table object containing files from the query.
    """

    # Convert a list of filters to a comma-separated string.
    if not isinstance(spectral_elements, str):
        spectral_elements = ",".join(spectral_elements)

    if ra == 0 and dec == 0 and radius == 180:
        # Perform an all-sky search.
        archive_search_url = ("https://hla.stsci.edu/cgi-bin/hlaSIAP.cgi?"
                              + "POS=0,0"
                              + "&size=180"
                              + "&imagetype={data_product}"
                              + "&inst={inst}"
                              + "&format=image/jpeg"
                              + "&autoscale={autoscale}"
                              + "&asinh={asinh}").format(**locals())
        if spectral_elements != "":
            archive_search_url += "&spectral_elt={spectral_elements}".format(
                **locals()
            )
    else:
        # Fetch jpeg images only in query.
        archive_search_url = ("https://hla.stsci.edu/cgi-bin/hlaSIAP.cgi?"
                              + "POS={ra},{dec}"
                              + "&size={radius}"
                              + "&imagetype={data_product}"
                              + "&inst={inst}"
                              + "&format=image/jpeg"
                              + "&autoscale={autoscale}"
                              + "&asinh={asinh}").format(**locals())
        if spectral_elements != "":
            archive_search_url += "&spectral_elt={spectral_elements}".format(
                **locals()
            )
    return Table.read(archive_search_url, format="votable")
