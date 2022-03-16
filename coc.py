# Send an image to the server to be labelled with the COC network.

import argparse

from send_data import ClientPortal

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Label an image.")
    parser.add_argument("Input", type=str, help="Input file path")
    parser.add_argument("Output", type=str, help="Output file path")
    parser.add_argument("--server", type=str, help="Server hostname",
                        default="raspberrypi.lan")
    args = parser.parse_args()

    portal = ClientPortal(server_hostname=args.server)
    portal.make_request(args.Input, args.Output)
