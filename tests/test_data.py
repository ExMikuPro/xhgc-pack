import struct

from PIL import Image

from xhcart_core.api import pack_header_icon
from xhcart_core.pipeline.build_data import BuildData


def test_build_index_preserves_data_offsets_when_sorting_names():
    builder = BuildData(pack_spec=None)
    index_content = builder.build_index([
        {
            'path': 'b.txt',
            'offset': 0,
            'size': 3,
            'crc32': 0xBBBBBBBB,
        },
        {
            'path': 'a.txt',
            'offset': 3,
            'size': 5,
            'crc32': 0xAAAAAAAA,
        },
    ])

    magic, version, entry_size, entry_count, entries_off, strings_off, strings_size, flags = struct.unpack_from(
        '<8sHHIIIII',
        index_content,
        0
    )
    assert magic == b'XHGCIDX2'
    assert version == 1
    assert entry_size == 32
    assert entry_count == 2
    assert entries_off == 32
    assert flags == 0

    entries = []
    for i in range(entry_count):
        cursor = entries_off + i * entry_size
        path_hash, path_off, data_offset, data_size, crc32, res_type, img_format, width, height, entry_flags, reserved = struct.unpack_from(
            '<IIIII BB H H H I',
            index_content,
            cursor
        )
        name_start = strings_off + path_off
        name_end = index_content.index(b'\x00', name_start)
        path = index_content[name_start:name_end].decode('utf-8')
        entries.append({
            'path_hash': path_hash,
            'path': path,
            'offset': data_offset,
            'size': data_size,
            'crc32': crc32,
            'type': res_type,
            'format': img_format,
            'width': width,
            'height': height,
            'flags': entry_flags,
            'reserved': reserved,
        })

    assert entries == [
        {
            'path_hash': builder._fnv1a_32('a.txt'),
            'path': 'a.txt',
            'offset': 3,
            'size': 5,
            'crc32': 0xAAAAAAAA,
            'type': 0,
            'format': 0,
            'width': 0,
            'height': 0,
            'flags': 0,
            'reserved': 0,
        },
        {
            'path_hash': builder._fnv1a_32('b.txt'),
            'path': 'b.txt',
            'offset': 0,
            'size': 3,
            'crc32': 0xBBBBBBBB,
            'type': 0,
            'format': 0,
            'width': 0,
            'height': 0,
            'flags': 0,
            'reserved': 0,
        },
    ]
    assert strings_size == len(b'a.txt\x00b.txt\x00')


def test_read_chunk_file_converts_res_image_to_bgra8888(tmp_path):
    image_path = tmp_path / 'sprite.png'
    Image.new('RGBA', (1, 1), (10, 20, 30, 40)).save(image_path)
    builder = BuildData(pack_spec=None)

    file_content, meta = builder._read_chunk_file(
        str(image_path),
        'RES',
        {
            'image_format': 'BGRA8888',
        }
    )

    assert file_content == bytes([30, 20, 10, 40])
    assert meta == {
        'type': BuildData.XHGC_RES_IMAGE,
        'format': BuildData.XHGC_IMG_BGRA8888,
        'width': 1,
        'height': 1,
    }


def test_read_chunk_file_resizes_res_image_when_preprocess_size_is_set(tmp_path):
    image_path = tmp_path / 'sprite.png'
    Image.new('RGBA', (1, 1), (10, 20, 30, 255)).save(image_path)
    builder = BuildData(pack_spec=None)

    file_content, meta = builder._read_chunk_file(
        str(image_path),
        'RES',
        {
            'image_format': 'BGRA8888',
            'image_preprocess': {
                'width': 2,
                'height': 1,
                'mode': 'cover',
                'resample': 'nearest',
            },
        }
    )

    assert file_content == bytes([
        30, 20, 10, 255,
        30, 20, 10, 255,
    ])
    assert meta['format'] == BuildData.XHGC_IMG_BGRA8888
    assert meta['width'] == 2
    assert meta['height'] == 1


def test_read_chunk_file_rejects_misspelled_res_image_format(tmp_path):
    image_path = tmp_path / 'sprite.png'
    Image.new('RGBA', (1, 1), (10, 20, 30, 40)).save(image_path)
    builder = BuildData(pack_spec=None)

    try:
        builder._read_chunk_file(str(image_path), 'RES', {'image_format': 'BRGA8888'})
        assert False, "Should reject unsupported RES image format"
    except ValueError as e:
        assert "Unsupported RES image_format" in str(e)


def test_read_chunk_file_can_wrap_res_image_with_metadata_header(tmp_path):
    image_path = tmp_path / 'sprite.png'
    Image.new('RGBA', (1, 1), (10, 20, 30, 40)).save(image_path)
    builder = BuildData(pack_spec=None)

    file_content, meta = builder._read_chunk_file(
        str(image_path),
        'RES',
        {
            'image_format': 'BGRA8888',
            'image_metadata': True,
        }
    )

    magic, version, header_size, width, height, fmt, bpp, flags, stride, data_size = struct.unpack_from(
        '<4sHHHHBBHII',
        file_content,
        0
    )

    assert magic == b'XIMG'
    assert version == 1
    assert header_size == 24
    assert width == 1
    assert height == 1
    assert fmt == 1
    assert bpp == 4
    assert flags == 0
    assert stride == 4
    assert data_size == 4
    assert file_content[header_size:] == bytes([30, 20, 10, 40])
    assert meta['format'] == BuildData.XHGC_IMG_BGRA8888
    assert meta['width'] == 1
    assert meta['height'] == 1


def test_cart_bin_uses_xhgcidx2_and_indexes_test_image(tmp_path):
    output_path = tmp_path / 'cart.bin'
    pack_header_icon('tests/pack.json', str(output_path))
    cart_data = output_path.read_bytes()

    index_offset, index_size, _ = struct.unpack_from('<QII', cart_data, 0x0F00 + 4 * 16)
    data_offset, _, _ = struct.unpack_from('<QII', cart_data, 0x0F00 + 5 * 16)
    index_content = cart_data[index_offset:index_offset + index_size]

    magic, version, entry_size, count, entries_off, strings_off, strings_size, flags = struct.unpack_from(
        '<8sHHIIIII',
        index_content,
        0
    )
    assert magic == b'XHGCIDX2'
    assert version == 1
    assert entry_size == 32
    assert flags == 0

    found_script = None
    found_image = None
    for i in range(count):
        cursor = entries_off + i * entry_size
        path_hash, path_off, data_off, size, crc32, res_type, img_format, width, height, entry_flags, reserved = struct.unpack_from(
            '<IIIII BB H H H I',
            index_content,
            cursor
        )
        path_start = strings_off + path_off
        path_end = index_content.index(b'\x00', path_start, strings_off + strings_size)
        path = index_content[path_start:path_end].decode('utf-8')
        entry = {
            'path_hash': path_hash,
            'data_off': data_off,
            'size': size,
            'crc32': crc32,
            'type': res_type,
            'format': img_format,
            'width': width,
            'height': height,
            'flags': entry_flags,
            'reserved': reserved,
        }
        if path == 'app/main.lua':
            found_script = entry
        if path == 'assets/test.png':
            found_image = {
                'path_hash': path_hash,
                'data_off': data_off,
                'size': size,
                'crc32': crc32,
                'type': res_type,
                'format': img_format,
                'width': width,
                'height': height,
                'flags': entry_flags,
                'reserved': reserved,
            }

    assert found_script is not None
    assert found_script['path_hash'] == BuildData(pack_spec=None)._fnv1a_32('app/main.lua')
    assert found_script['type'] == BuildData.XHGC_RES_SCRIPT
    assert found_script['format'] == BuildData.XHGC_IMG_NONE
    assert found_script['width'] == 0
    assert found_script['height'] == 0

    assert found_image is not None
    assert found_image['path_hash'] == BuildData(pack_spec=None)._fnv1a_32('assets/test.png')
    assert found_image['size'] == 200 * 200 * 4
    assert found_image['type'] == BuildData.XHGC_RES_IMAGE
    assert found_image['format'] == BuildData.XHGC_IMG_BGRA8888
    assert found_image['width'] == 200
    assert found_image['height'] == 200
    assert found_image['flags'] == 0
    assert found_image['reserved'] == 0
    assert len(
        cart_data[data_offset + found_image['data_off']:data_offset + found_image['data_off'] + found_image['size']]
    ) == found_image['size']
