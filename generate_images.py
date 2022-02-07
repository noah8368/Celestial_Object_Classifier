'''Download and process raw image data from the Hubble Legacy Archive

Define the AstroImgManager type, which contains routines to collect raw image
data, perform image stacking, and further filtering.
'''

import cv2 as cv
import glob
import numpy as np
import os
import shutil

from astropy.table import Table
from custom_exceptions import EmptySearch, NotEnoughExposures
from distutils.ccompiler import gen_lib_options
from image_stacking.auto_stack import stackImagesECC
from requests import get
from urllib.error import URLError


class AstroImgManager:
    IMG_EXT = ".jpeg"

    def __init__(self):
        self.data_path = os.path.join(os.curdir, "images")
        if not os.path.exists(self.data_path):
            os.mkdir(self.data_path)

    def gen_img_set(self, num_images, process_manually=False):
        """Generates a set of processed images.

        Randomly gens a set of celestial coordinates and saves a single
        processed image for each coordinate. If a connection error occurs
        during image processing for a given coordinate, formation of this image
        is skipped.

        Args:
            num_images: Number of images in the data set.
            process_manually: If true, download exposures from the Hubble
                              Legacy Archive and manually process them rather
                              than pre-processed data.
        """

        def gen_rand_loc():
            ra = round(np.random.uniform(0, 360), 3)
            dec = round(np.rad2deg(np.arcsin(np.random.uniform(-1, 1))), 3)
            return ra, dec

        def remove_exposures():
            # Remove exposures from an in-progress image compilation.
            exposure_files = glob.glob(os.path.join(self.data_path,
                                                    "exposure_*"
                                                    + self.IMG_EXT))
            for file in exposure_files:
                os.remove(file)

        # Generate num_images images and save them in the "images" directory.
        prev_locs = []
        for img_count in range(num_images):
            ra, dec = gen_rand_loc()

            while True:
                if (ra, dec) in prev_locs:
                    # Generate a new location if the current location has
                    # already been searched.
                    ra, dec = gen_rand_loc()
                    continue

                try:
                    self.__fetch_img(ra, dec, process_manually)
                except (ConnectionError, URLError):
                    if process_manually:
                        remove_exposures()

                    # Retry the same coordinate pair if the connection fails.
                    continue
                except (cv.error, EmptySearch, NotEnoughExposures, ValueError):
                    if process_manually:
                        remove_exposures()

                    # Generate a new location if the search results in any
                    # other exceptions and try again.
                    ra, dec = gen_rand_loc()
                    continue

                prev_locs.append((ra, dec))
                break

    def __enhance_contrast(self, img_matrix, bins=256):
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

    def __fetch_img(self, ra, dec, processing_manually):
        """Generates a processed image from the Hubble Legacy Archive.

        Args:
            ra, dec: Right ascension and declination. Central position in deg
                     for the cutout.
            radius: Radius of the cutout, in degrees.
        """

        SEARCH_RADIUS = 0.4
        MIN_NUM_EXPOSURES = 5
        try:
            if processing_manually:
                img_table = self.__query_hubble_legacy_archive(ra, dec,
                                                               SEARCH_RADIUS,
                                                               "exposure",
                                                               "WFC3")
            else:
                img_table = self.__query_hubble_legacy_archive(ra, dec,
                                                               SEARCH_RADIUS,
                                                               "combined",
                                                               "WFC3")
            if len(img_table) == 0:
                raise EmptySearch
        except ValueError:
            print("ERROR: Invalid query options")
        print("\nProcessing data at location RA:", str(ra) + "° DEC:",
              str(dec) + "°\n")

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

            # Download exposures for each position.
            exposure_count = 0
            exposure_path_list = []
            for exposure_url in exposure_urls:
                exposure_count += 1
                exposure_path = os.path.join(self.data_path,
                                             "exposure_" + str(exposure_count)
                                             + self.IMG_EXT)
                exposure_path_list.append(exposure_path)
                self.__save_img(exposure_url, exposure_path)
                self.__straighten_img(exposure_path)

            # Combine exposures for the chosen location into a single image.
            combined_img = stackImagesECC(exposure_path_list)
            ra, dec = list(grouped_img_urls.keys())[loc_index]
            img_path = os.path.join(self.data_path, "RA_" + str(ra) + "__DEC_"
                                    + str(dec) + self.IMG_EXT)

            # Remove downloaded exposures once they've been combined.
            for exposure_f in exposure_path_list:
                os.remove(exposure_f)

            filtered_img = cv.bilateralFilter(combined_img, 5, 75, 75)
            filtered_img = self.__enhance_contrast(filtered_img)
            cv.imwrite(img_path, filtered_img)
        else:
            # Save the first image of the first location from the query.
            ra, dec = list(grouped_img_urls.keys())[0]
            img_url = list(grouped_img_urls.values())[0][0]
            img_path = os.path.join(self.data_path, "RA_" + str(ra) + "__DEC_"
                                    + str(dec) + self.IMG_EXT)
            self.__save_img(img_url, img_path)
            self.__straighten_img(img_path)

    def __save_img(self, url, path):
        # Ensure the HTTPS reply's status code indicates success (OK status)
        # before continuing.
        req = get(url, stream=True)
        OK_STATUS = 200
        if req.status_code == OK_STATUS:
            req.raw.decode_content = True
        else:
            raise ConnectionError()
        img_file = open(path, "wb")
        shutil.copyfileobj(req.raw, img_file)
        img_file.close()

    def __find_corners(self):
        # TODO (Madison): Paste your code here.
        pass

    def __straighten_img(self, img_path):
        # TODO (Madison): Paste your code here.
        pass

    def __query_hubble_legacy_archive(self, ra, dec, radius, data_product,
                                      inst, spectral_elements=(),
                                      autoscale=99.5, asinh=1):
        """Queries image data from the Hubble Legacy Archive.

        Args:
            ra, dec: Right ascension and declination. Central position in deg
                     for the cutout.
            radius: Radius of the cutout, in degrees.
            data_product: Type of image to retrieve. Options are "best",
                          "exposure", "combined", "mosaic", "color", "hlsp",
                          and "all".
            inst: Instrument to collect data from on Hubble Space Telescope
            format: Queried data file format.
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


if __name__ == "__main__":
    img_manager = AstroImgManager()
    img_manager.gen_img_set(1, process_manually=True)
