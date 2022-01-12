'''Implement image processing functions

Define routines to collect and process data from the Hubble Legacy Archive.
'''

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import shutil

from astropy.table import Table
from requests import get


class AstroImgManager:
    def fetch_images(self):
        # Perform an all-sky search.
        img_table = self.__query_hubble_legacy_archive(210.802, 54.349, 0.1,
                                                       "combined", "WFC3")
        # Save a random image.
        num_img = len(img_table)
        self.__save_image(img_table["URL"][np.random.randint(num_img)])

        # Display the image.
        img = mpimg.imread(self.SAMPLE_IMG_NAME)
        plt.imshow(img)
        plt.show()

    def __save_image(self, url):
        req = get(url, stream=True)
        # Ensure the HTTPS reply's status code indicates success (OK status).
        OK_STATUS = 200
        if req.status_code == OK_STATUS:
            req.raw.decode_content = True
        else:
            raise ConnectionError()
        img_file = open(self.SAMPLE_IMG_NAME, "wb")
        shutil.copyfileobj(req.raw, img_file)
        img_file.close()

    def __query_hubble_legacy_archive(self, ra, dec, size, data_product, inst,
                                      spectral_elements=(), autoscale=99.5,
                                      asinh=1, format="image/jpeg"):
        """Queries image data from the Hubble Legacy Archive.

        Args:
            ra, dec: Right ascension and declination. Central position in deg
                     for the cutout.
            size: Radius of the cutout, in degrees.
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
            A astropy Table object containing files from the query.
        """

        # Convert a list of filters to a comma-separated string.
        if not isinstance(spectral_elements, str):
            spectral_elements = ",".join(spectral_elements)

        archive_search_url = ("https://hla.stsci.edu/cgi-bin/hlaSIAP.cgi?"
                              + "POS={ra},{dec}"
                              + "&size={size}"
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

    SAMPLE_IMG_NAME = "rand_img.jpeg"


def process_data():
    # TODO: Implement. (Madison)
    return None
