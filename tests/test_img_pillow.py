from PIL import Image

from xhcart_core.tools.img_pillow import process_image


def test_process_image_outputs_argb8888_byte_order(tmp_path):
    image_path = tmp_path / 'pixel.png'
    Image.new('RGBA', (1, 1), (10, 20, 30, 40)).save(image_path)

    raw_data = process_image(
        image_path=image_path,
        width=1,
        height=1,
        mode='cover',
        resample='nearest',
    )

    assert raw_data == bytes([40, 10, 20, 30])


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

    assert raw_data[:4] == bytes([128, 1, 2, 3])
