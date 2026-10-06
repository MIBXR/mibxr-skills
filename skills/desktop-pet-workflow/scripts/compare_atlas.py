#!/usr/bin/env python3
"""Check that decoded pixels outside allowed atlas rows remain unchanged."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageChops


def compare(before, after, columns, rows, allowed):
    if columns < 1 or rows < 1 or not allowed <= set(range(1, rows + 1)):
        raise ValueError('Grid sizes must be positive; allowed rows are 1-based within the grid')
    with Image.open(before) as source, Image.open(after) as revised:
        if source.size != revised.size:
            raise ValueError('Before and after image dimensions differ')
        width, height = source.size
        if width % columns or height % rows:
            raise ValueError('Image dimensions must divide evenly by the grid')
        modes = [source.mode, revised.mode]
        left, right = source.convert('RGBA'), revised.convert('RGBA')
    changed = []
    row_height = height // rows
    for index in range(rows):
        box = (0, index * row_height, width, (index + 1) * row_height)
        difference = ImageChops.difference(left.crop(box), right.crop(box))
        red, green, blue, alpha = difference.split()
        mask = ImageChops.lighter(ImageChops.lighter(red, green), ImageChops.lighter(blue, alpha))
        pixels = sum(mask.histogram()[1:])
        if pixels:
            changed.append({'row': index + 1, 'changed_pixels': pixels})
    outside = [row['row'] for row in changed if row['row'] not in allowed]
    return {'width': width, 'height': height, 'columns': columns, 'rows': rows,
            'input_modes': modes, 'allowed_rows': sorted(allowed), 'changed_rows': changed,
            'unexpected_rows': outside, 'passed': not outside,
            'before_sha256': hashlib.sha256(Path(before).read_bytes()).hexdigest(),
            'after_sha256': hashlib.sha256(Path(after).read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--columns', type=int, required=True)
    parser.add_argument('--rows', type=int, required=True)
    parser.add_argument('--allow-rows', default='', help='Comma-separated 1-based row numbers; empty permits no change')
    args = parser.parse_args()
    try:
        allowed = {int(value.strip()) for value in args.allow_rows.split(',') if value.strip()}
        result = compare(args.before, args.after, args.columns, args.rows, allowed)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
