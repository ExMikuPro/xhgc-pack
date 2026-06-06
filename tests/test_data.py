import struct

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

    entry_count = struct.unpack_from('<I', index_content, 0)[0]
    assert entry_count == 2

    entries = []
    cursor = 8
    for _ in range(entry_count):
        data_offset, data_size, crc32, name_len = struct.unpack_from('<IIIB', index_content, cursor)
        name_start = cursor + 16
        name_end = name_start + name_len
        entries.append({
            'path': index_content[name_start:name_end].decode('utf-8'),
            'offset': data_offset,
            'size': data_size,
            'crc32': crc32,
        })
        cursor = name_end

    assert entries == [
        {
            'path': 'a.txt',
            'offset': 3,
            'size': 5,
            'crc32': 0xAAAAAAAA,
        },
        {
            'path': 'b.txt',
            'offset': 0,
            'size': 3,
            'crc32': 0xBBBBBBBB,
        },
    ]
