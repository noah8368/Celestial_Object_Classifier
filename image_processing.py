'''Implement image processing functions

Define routines to collect and process data from the Hubble Legacy Archive.
'''

import os

from astropy.table import Table
from getpass import getpass
from io import BytesIO
from PIL import Image
from requests import get


class AstroImgManager:
    """def __init__(self):
        if not os.environ.get('CASJOBS_USERID'):
            os.environ['CASJOBS_USERID'] = input('Enter Casjobs UserID: ')
        if not os.environ.get('CASJOBS_PW'):
            os.environ['CASJOBS_PW'] = getpass('Enter Casjobs password: ')
    """
    def fetch_images(self):
        img_table = self.__query_hubble_legacy_archive(0, 0, 180, "exposure",
                                                       "WFC3")
        img_table.pprint_all()

    def __get_image(self, url):
        req = get(url)
        return Image.open(BytesIO(req.content))

    def __query_hubble_legacy_archive(self, ra, dec, size, data_product, inst,
                                      spectral_elements=(), autoscale=99.5,
                                      asinh=1, naxis=512, format="jpeg"):
        """Queries image data from the Hubble Legacy Archive.

        Args:
            ra, dec: Right ascension and declination. Central position in deg
                     for the cutout.
            size: Radius of the cutout, in degrees.
            data_product: A specifier to indicate the selection of monochrome
                       or color images.
            inst: Instrument to collect data from on Hubble Space Telescope
            format: Queried data file format.
            spectral elements: A tuple of strings of filter color identifiers.
            autoscale: Percentage of image histogram to retain.
            asinh: If nonzero value, use Lupton asinh contrast algorithm.
            naxis: Image width, in pixels.
            format: Image file format.

        Returns:
            A astropy Table object containing files from the query.
        """

        # Convert a list of filters to a comma-separated string.
        if not isinstance(spectral_elements, str):
            spectral_elements = ",".join(spectral_elements)

        archive_search_url = ("https://hla.stsci.edu/cgi-bin/hlaSIAP.cgi?"
                              + "pos={ra},{dec}"
                              + "&size={size}"
                              + "&imagetype={data_product}"
                              + "&inst={inst}"
                              + "&format=image/{format}"
                              + "&spectral_elt={spectral_elements}"
                              + "&autoscale={autoscale}"
                              + "&asinh={asinh}"
                              + "&naxis={naxis}").format(**locals())
        print(archive_search_url)
        return Table.read(archive_search_url, format="votable")

def process_data():
    # TODO: Implement. (Madison)
    return None
