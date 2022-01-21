'''Download and process raw image data from the Hubble Legacy Archive

Define the AstroImgManager type, which contains routines to collect raw image
data, perform image stacking, and further filtering.
'''

import cv2 as cv
import numpy as np
import os
import shutil

from astropy.table import Table
from image_stacking.auto_stack import stackImagesECC
from requests import get


class AstroImgManager:
    def __init__(self):
        self.data_path = os.path.join(os.curdir, "images")
        if not os.path.exists(self.data_path):
            os.mkdir(self.data_path)

    def fetch_image(self, ra, dec):
        """Generates a set of processed images from the Hubble Legacy Archive.

        Args:
            ra, dec: Right ascension and declination. Central position in deg
                        for the cutout.
            radius: Radius of the cutout, in degrees.
        """

        SEARCH_RADIUS = 0.4
        try:
            img_table = self.__query_hubble_legacy_archive(ra, dec,
                                                           SEARCH_RADIUS,
                                                           "exposure", "WFC3")
        except ValueError:
            print("ERROR: Invalid query options")
        print("Processing exposures at position", str(ra) + ", " + str(dec)
              + "...")

        # Group exposures by right ascension and declination.
        grouped_exposure_urls = {}
        for entry in img_table:
            exposure_loc = (entry["RA"], entry["DEC"])
            if exposure_loc in grouped_exposure_urls:
                grouped_exposure_urls[exposure_loc].append(entry["URL"])
            else:
                grouped_exposure_urls[exposure_loc] = [entry["URL"]]

        # Select the image with the most exposures for stacking.
        image_index = np.argmax([len(url_list) for url_list in
                                list(grouped_exposure_urls.values())])
        exposure_urls = list(grouped_exposure_urls.values())[image_index]

        # Download exposures for each position.
        exposure_count = 0
        exposure_path_list = []
        for exposure_url in exposure_urls:
            exposure_count += 1
            exposure_path = os.path.join(self.data_path,
                                         "exposure_" + str(exposure_count)
                                         + ".jpeg")
            exposure_path_list.append(exposure_path)
            self.__save_image(exposure_url, exposure_path)

        combined_img = stackImagesECC(exposure_path_list)
        ra, dec = list(grouped_exposure_urls.keys())[image_index]
        img_name = os.path.join(self.data_path, str(ra) + "_" + str(dec)
                                + ".jpeg")
        cv.imwrite(img_name, combined_img)

        # Remove downloaded exposures once they've been combined.
        for exposure_f in exposure_path_list:
            os.remove(exposure_f)

        # TODO (Madison): Perform further image filtering.

    def __save_image(self, url, path):
        # Send an HTTPS request to fetch image data. Ensure the HTTPS reply's
        # status code indicates success (OK status) before continuing.
        req = get(url, stream=True)  # TODO: Catch ConnectionError exceptions.
        OK_STATUS = 200
        if req.status_code == OK_STATUS:
            req.raw.decode_content = True
        else:
            raise ConnectionError()
        img_file = open(path, "wb")
        shutil.copyfileobj(req.raw, img_file)
        img_file.close()

    def __query_hubble_legacy_archive(self, ra, dec, radius, data_product, inst,
                                      spectral_elements=(), autoscale=99.5,
                                      asinh=1, format="image/jpeg"):
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

        archive_search_url = ("https://hla.stsci.edu/cgi-bin/hlaSIAP.cgi?"
                              + "POS={ra},{dec}"
                              + "&size={radius}"
                              + "&imagetype={data_product}"
                              + "&inst={inst}"
                              + "&format={format}"
                              + "&autoscale={autoscale}"
                              + "&asinh={asinh}").format(**locals())
        if spectral_elements != "":
            archive_search_url += "&spectral_elt={spectral_elements}".format(
                **locals()
            )
        return Table.read(archive_search_url, format="votable")

if __name__ == "__main__":
    img_manager = AstroImgManager()
    img_manager.fetch_image(180.468, -18.866)
