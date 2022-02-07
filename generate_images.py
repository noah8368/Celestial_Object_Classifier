'''Download and process raw image data from the Hubble Legacy Archive

Define the AstroImgManager type, which contains routines to collect raw image
data, perform image stacking, and further filtering.
'''

import cv2 as cv
import glob
import math
import numpy as np
import operator
import os
import shutil

from astropy.table import Table
from custom_exceptions import EmptySearch, NotEnoughExposures
from distutils.ccompiler import gen_lib_options
from image_stacking.auto_stack import stackImagesECC
from requests import get
from scipy import ndimage
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
        """Applies histogram equalization to improve image contrast."""
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
        """Downloads the image from a given url.
        
        Args:
            url: Location to download image from.
            path: Location to save image to locally.
        """
        req = get(url, stream=True)
        OK_STATUS = 200
        # Ensure the HTTPS reply's status code indicates success (OK status).
        if req.status_code == OK_STATUS:
            req.raw.decode_content = True
        else:
            raise ConnectionError()
        img_file = open(path, "wb")
        shutil.copyfileobj(req.raw, img_file)
        img_file.close()

    def __find_corners(self, image, comparator, pixel_value):
        """Returns the location of the corners of an image.

        image: numpy array containing pixel values.
        comparator: TODO (Madison): Describe this function argument.
        pixel_value: TODO (Madison): Describe this function argument.
        """
        num_rows = np.shape(image)[0]
        num_cols = np.shape(image)[1]

        # TODO (Madison): Give this variable a more descriptive name.
        flag = False
        # Find corner on top edge
        for i in range(num_rows):
            for j in range(num_cols):
                if comparator(image[i, j], pixel_value):
                    top_corner = (i, j, image[i, j])
                    flag = True
                    break
            if flag == True:
                break

        flag = False
        # Find corner on bottom edge
        # TODO (Madison): Use more descriptive index names than "i" and "j".
        for i in reversed(range(num_rows)):
            for j in range(num_cols):
                if comparator(image[i, j], pixel_value):
                    bottom_corner = (i, j, image[i, j])
                    flag = True
                    break
            if flag == True:
                break

        flag = False
        # Find corner on left edge
        # TODO (Madison): Whenever possible, use numpy functions and arrays
        # rather than normal python lists in your code.
        for j in range(num_cols):
            for i in range(num_rows):
                if comparator(image[i, j], pixel_value):
                    left_corner = (i, j, image[i, j])
                    flag = True
                    break
            if flag == True:
                break

        flag = False
        # Find corner on right edge
        for j in reversed(range(num_cols)):
            for i in range(num_rows):
                if comparator(image[i, j], pixel_value):
                    right_corner = (i, j, image[i, j])
                    flag = True
                    break
            # TODO (Madison): A cleaner way of checking if "flag == True" is
            # by simply writing "if flag".
            if flag == True:
                break

        """TODO (Madison): The preceding four for-loops may be combined into
        a single loop to improve the efficiency of this code.
        """
        
        return top_corner, bottom_corner, left_corner, right_corner

    def __straighten_img(self, img_path):
        """Rotates images to ensure they're rectangular.
        
        Args:
            img_path: Local path to image.
        """
        image_src = cv.imread(img_path)
        image_data = cv.cvtColor(image_src, cv.COLOR_BGR2GRAY)

        # TODO (Madison): Remove this. This is an unnecessary comment. What
        # you're doing here is already clear by the function name. (1)
        # Find corners
        # TODO (Madison): Lines shouldn't be over 80 characters long. (2)
        top_corner, bottom_corner, left_corner, right_corner = self.__find_corners(image_data, operator.lt, 255)
        
        # TODO (Madison): Comments should end in a period. (3)
        # Find angle relative to x axis
        # TODO (Madison): See (2).
        theta = math.tan((right_corner[0] - top_corner[0])/(right_corner[1] - top_corner[1]))
        theta = int(theta*180/np.pi)
        
        # TODO (Madison): See (1) and (3).
        # Rotate image
        rotated = ndimage.rotate(image_data, 90-theta)
        
        # TODO (Madison): See (1), (2) and (3).
        # Find corners
        top_corner_r, bottom_corner_r, left_corner_r, right_corner_r = self.__find_corners(rotated, operator.gt, 0)
        
        # TODO (Madison): You can make this one line: "num_rows, num_cols = ..."
        num_rows = np.shape(rotated)[0]
        num_cols = np.shape(rotated)[1]
        
        # TODO (Madison): Use more descriptive index names that "i" and "j".
        # Find top edge
        for i in range(top_corner_r[0], num_rows):
            j = top_corner_r[1]
            # TODO (Madison): Avoid using "magic numbers". Save 255 to a
            # descriptive variable name such as "WHITE_PX_VAL" (using all caps
            # and underscores indicates this is a constant value).
            if rotated[i, j] < 255:
                top_edge = (i, j, rotated[i, j])
                break
                    
        # Find bottom edge
        for i in range(bottom_corner_r[0], 0, -1):
                j = bottom_corner_r[1]
                if rotated[i, j] < 255:
                    bottom_edge = (i, j, rotated[i, j])
                    break

        # Find left edge
        for j in range(left_corner_r[1], num_cols):
            i = left_corner_r[0]
            if rotated[i, j] < 255:
                left_edge = (i, j, rotated[i, j])
                break

        # Find right edge
        for j in range(right_corner_r[1], 0, -1):
            i = right_corner_r[0]
            if rotated[i, j] < 255:
                right_edge = (i, j, rotated[i, j])
                break
          
        # Crop image
        # TODO (Madison): Give this variable a name that desribes what the
        # value it holds is, not what you've done to it. A good example might
        # be "oriented_img" with a comment explaining that you're cropped the
        # image in this line.
        rotated_cropped = rotated[top_edge[0]:bottom_edge[0], left_edge[1]:right_edge[1]]
        
        cv.imwrite(img_path, rotated_cropped)

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
