'''Implement image processing functions

Define routines to collect and process data from the Hubble Legacy Archive.
'''

from astropy.table import Table
from PIL import Image
from io import BytesIO
import requests


# TODO (Noah): Encapsulate query_hubble_legacy_archive() and get_image()
def query_hubble_legacy_archive(ra, dec, size, imagetype, inst,
                                spectral_elements=(), autoscale=99.5, asinh=1,
                                naxis=512):
    """Queries image data from the Hubble Legacy Archive.

    Args:
        ra, dec: Right ascension and declination. Central position in degrees
                 for the cutout.
        size: Radius of the cutout, in degrees.
        imagetype: A specifier to indicate the selection of monochrome or color
                   images.
        inst: Instrument to collect data from on Hubble Space Telescope
        format: Queried data file format.
        spectral elements: A tuple of strings of color identifiers for filters.
        autoscale: Percentage of image histogram to retain.
        asinh: If set to a nonzero value, use Lupton asinh contrast algorithm.
        naxis: Image width, in pixels.

    Returns:
        A astropy Table object containing files from the query.
    """

    # Convert a list of filters to a comma-separated string.
    if not isinstance(spectral_elements, str):
        spectral_elements = ",".join(spectral_elements)

    # TODO (Noah): Set the username and password as local vars for query.
    archive_search_url = ("https://hla.stsci.edu/cgi-bin/hlaSIAP.cgi?pos={ra},"
                          + "{dec}&size={size}&imagetype={imagetype}"
                          + "&inst={inst}&format=image/jpeg"
                          + "&spectral_elt={spectral_elements}"
                          + "&autoscale={autoscale}&asinh={asinh}"
                          + "&naxis={naxis}").format(**locals())

    return Table.read(archive_search_url, format="votable")


def get_image(url):
    r = requests.get(url)
    im = Image.open(BytesIO(r.content))
    return im


def fetch_images():
    # TODO (Noah): Use query_hubble_legacy_archive() and get_image() to download
    #              astrophotography data locally.
    return None


def process_data():
    # TODO: Implement. (Madison)
    return None
