# Test the ServerPortal object.

from send_data import ServerPortal
from shutil import rmtree
import os
from detect import run

coc_weights = 'weights/coc_weights.pt'
input_images = 'images_to_label'
output_images = 'labeled_images'

server = ServerPortal()

image_name = 'recv.jpeg'

received_img = os.path.join(input_images, image_name)

while True:
    server.recv(received_img)

    run(weights=coc_weights,  # model.pt path(s)
            source=input_images,  # file/dir/URL/glob, 0 for webcam
            project=output_images,  # save results to project/name
            name=".",  # save results to project/name
            )

    server.send(os.path.join(output_images, image_name))

    rmtree(output_images)
