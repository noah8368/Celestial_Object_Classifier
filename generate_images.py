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
                zoomed = self.__is_zoomed_in(exposure_path)
                if zoomed:
                    self.__straighten_zoomed_img(exposure_path)
                else:
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

    def __is_zoomed_in(self, img_path):
        """Checks to see whether an image is zoomed in. Returns True/False.
        
        Args:
        img_path: Local path to image.
        """
        WHITE_PX_VAL = 255
        
        image_src = cv.imread(img_path)
        image_data = cv.cvtColor(image_src, cv.COLOR_BGR2GRAY)
        
        num_rows = np.shape(image_data)[0]
        num_cols = np.shape(image_data)[1]

        zoomed_in = False
        first_point_row_idx = None
        second_point_row_idx = None

        for row_idx in range(num_rows):
            if image_data[row_idx, 0] < WHITE_PX_VAL:
                first_point_row_idx = row_idx
                break

        for row_idx in reversed(range(num_rows)):
            if image_data[row_idx, 0] < WHITE_PX_VAL:
                second_point_row_idx = row_idx
                break

        if (first_point_row_idx != second_point_row_idx) and
            (first_point_row_idx != None) and (second_point_row_idx != None):
            zoomed_in = True

        return zoomed_in
    
    def __find_corners(self, image, greater_or_less_than, pixel_value):
        """Returns the location of the corners of an image.

        image: numpy array containing pixel values.
        greater_or_less_than: either operator.lt or operator.gt depending on
        whether we want to use < or >.
        pixel_value: either 255 or 0.
        """
        num_rows = np.shape(image)[0]
        num_cols = np.shape(image)[1]

        corner_assigned = False
        # Find corner on top edge.
        for row_idx in range(num_rows):
            for col_idx in range(num_cols):
                if greater_or_less_than(image[row_idx, col_idx], pixel_value):
                    top_corner = (row_idx, col_idx, image[row_idx, col_idx])
                    corner_assigned = True
                    break
            if corner_assigned:
                break

        corner_assigned = False
        # Find corner on bottom edge.
        for row_idx in reversed(range(num_rows)):
            for col_idx in range(num_cols):
                if greater_or_less_than(image[row_idx, col_idx], pixel_value):
                    bottom_corner = (row_idx, col_idx, image[row_idx, col_idx])
                    corner_assigned = True
                    break
            if corner_assigned:
                break

        corner_assigned = False
        # Find corner on left edge.
        for col_idx in range(num_cols):
            for row_idx in range(num_rows):
                if greater_or_less_than(image[row_idx, col_idx], pixel_value):
                    left_corner = (row_idx, col_idx, image[row_idx, col_idx])
                    corner_assigned = True
                    break
            if corner_assigned:
                break

        corner_assigned = False
        # Find corner on right edge.
        for col_idx in reversed(range(num_cols)):
            for row_idx in range(num_rows):
                if greater_or_less_than(image[row_idx, col_idx], pixel_value):
                    right_corner = (row_idx, col_idx, image[row_idx, col_idx])
                    corner_assigned = True
                    break
            if corner_assigned:
                break
        
        return top_corner, bottom_corner, left_corner, right_corner

    def __straighten_img(self, img_path):

        """Rotates and crops images to ensure they're rectangular.
        Args:
            img_path: Local path to image.
        """
        image_src = cv.imread(img_path)
        image_data = cv.cvtColor(image_src, cv.COLOR_BGR2GRAY)

        WHITE_PX_VAL = 255
        top_corner, bottom_corner, left_corner, right_corner =
            self.__find_corners(image_data, operator.lt, WHITE_PX_VAL)
        
        # Find angle relative to x axis.
        theta = math.tan((right_corner[0] - top_corner[0])/(right_corner[1]
            - top_corner[1]))
        theta = int(theta*180/np.pi)
        
        # Rotate image by angle theta.
        rotated = ndimage.rotate(image_data, 90-theta)
        
        BLACK_PX_VAL = 0
        top_corner_r, bottom_corner_r, left_corner_r, right_corner_r =
            self.__find_corners(rotated, operator.gt, BLACK_PX_VAL)
        
        num_rows, num_cols = np.shape(rotated)[0], np.shape(rotated)[1]
        
        # Find top edge.
        for top_r_idx in range(top_corner_r[0], num_rows):
            top_c_idx = top_corner_r[1]

            if rotated[top_r_idx, top_c_idx] < WHITE_PX_VAL:
                top_edge = (top_r_idx, top_c_idx, rotated[top_r_idx,
                    top_c_idx])
                break
                    
        # Find bottom edge.
        for bottom_r_idx in range(bottom_corner_r[0], 0, -1):
                bottom_c_idx = bottom_corner_r[1]
                if rotated[bottom_r_idx, bottom_c_idx] < WHITE_PX_VAL:
                    bottom_edge = (bottom_r_idx, bottom_c_idx,
                        rotated[bottom_r_idx, bottom_c_idx])
                    break

        # Find left edge.
        for left_c_idx in range(left_corner_r[1], num_cols):
            left_r_idx = left_corner_r[0]
            if rotated[left_r_idx, left_c_idx] < WHITE_PX_VAL:
                left_edge = (left_r_idx, left_c_idx,
                    rotated[left_r_idx, left_c_idx])
                break

        # Find right edge.
        for right_c_idx in range(right_corner_r[1], 0, -1):
            right_r_idx = right_corner_r[0]
            if rotated[right_r_idx, right_c_idx] < WHITE_PX_VAL:
                right_edge = (right_r_idx, right_c_idx,
                    rotated[right_r_idx, right_c_idx])
                break
          
        #Crop image.
        oriented_img = rotated[top_edge[0]:bottom_edge[0],
            left_edge[1]:right_edge[1]]
        
        cv.imwrite(img_path, oriented_img)
        
    def __straighten_zoomed_img(self, img_path):
        """Crops zoomed images to ensure they're rectangular.
        
        Args:
            img_path: Local path to image.
        """
        WHITE_PX_VAL = 255
        
        image_src = cv.imread(img_path)
        image_data = cv.cvtColor(image_src, cv.COLOR_BGR2GRAY)
        
        num_rows = np.shape(image_data)[0]
        num_cols = np.shape(image_data)[1]
        
        corner_assigned = False
        for row_idx in range(num_rows):
            for col_idx in range(num_cols):
                if image_data[row_idx, col_idx] < WHITE_PX_VAL:
                    left_upper = (row_idx, col_idx,
                        image_data[row_idx, col_idx])
                    corner_assigned = True
                    break
                else:
                    row_idx = row_idx + 1
                    col_idx = col_idx + 1
            if corner_assigned:
                break

        corner_assigned = False
        for row_idx in range(num_rows):
            for col_idx in reversed(range(num_cols)):
                if image_data[row_idx, col_idx] < WHITE_PX_VAL:
                    right_upper = (row_idx, col_idx,
                        image_data[row_idx, col_idx])
                    corner_assigned = True
                    break
                else:
                    row_idx = row_idx + 1
                    col_idx = col_idx - 1
            if corner_assigned:
                break

        corner_assigned = False
        for row_idx in reversed(range(num_rows)):
            for col_idx in range(num_cols):
                if image_data[row_idx, col_idx] < WHITE_PX_VAL:
                    left_lower = (row_idx, col_idx,
                        image_data[row_idx, col_idx])
                    corner_assigned = True
                    break
                else:
                    row_idx = row_idx - 1
                    col_idx = col_idx + 1
            if corner_assigned:
                break

        corner_assigned = False
        for row_idx in reversed(range(num_rows)):
            for col_idx in reversed(range(num_cols)):
                if image_data[row_idx, col_idx] < WHITE_PX_VAL:
                    right_lower = (row_idx, col_idx,
                        image_data[row_idx, col_idx])
                    corner_assigned = True
                    break
                else:
                    row_idx = row_idx - 1
                    col_idx = col_idx - 1
            if corner_assigned:
                break
        
        #Find top value.
        if left_upper[0] > right_upper[0]:
            top_value = left_upper
        else:
            top_value = right_upper

        #Find bottom value.
        if left_lower[0] < right_lower[0]:
            bottom_value = left_lower
        else:
            bottom_value = right_lower

        #Find left value.
        if left_upper[1] > left_lower[1]:
            left_value = left_upper
        else:
            left_value = left_lower

        #Find right value.
        if right_upper[1] < right_lower[1]:
            right_value = right_upper
        else:
            right_value = right_lower
            
            
        #Crop image.
        oriented_zoomed_img = image_data[top_value[0]:bottom_value[0],
            left_value[1]:right_value[1]]
        
        cv.imwrite(img_path, oriented_zoomed_img)
        
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
