from PIL import Image

from xhcart_core.tools.img_pillow import process_image, process_resource_image


def test_process_image_outputs_bgra_byte_order(tmp_path):
    image_path = tmp_path / 'pixel.png'
    Image.new('RGBA', (1, 1), (10, 20, 30, 40)).save(image_path)

    raw_data = process_image(
        image_path=image_path,
        width=1,
        height=1,
        mode='cover',
        resample='nearest',
    )

    assert raw_data == bytes([30, 20, 10, 40])


def test_process_image_accepts_aarrggbb_background(tmp_path):
    image_path = tmp_path / 'transparent.png'
    Image.new('RGBA', (1, 1), (0, 0, 0, 0)).save(image_path)

    raw_data = process_image(
        image_path=image_path,
        width=2,
        height=1,
        mode='contain',
        background='#80010203',
        resample='nearest',
    )

    assert raw_data[:4] == bytes([3, 2, 1, 128])


def test_process_resource_image_keeps_source_size_by_default(tmp_path):
    image_path = tmp_path / 'pixels.png'
    image = Image.new('RGBA', (2, 1))
    image.putpixel((0, 0), (10, 20, 30, 40))
    image.putpixel((1, 0), (50, 60, 70, 80))
    image.save(image_path)

    raw_data = process_resource_image(image_path=image_path)

    assert raw_data == bytes([
        30, 20, 10, 40,
        70, 60, 50, 80,
    ])
