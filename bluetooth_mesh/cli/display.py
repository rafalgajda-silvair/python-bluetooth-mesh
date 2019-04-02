#
# python-bluetooth-mesh - Bluetooth Mesh for Python
#
# Copyright (C) 2019  SILVAIR sp. z o.o.
#
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
#
from PIL import Image, ImageFont, ImageDraw
import string


class Font:
    LETTERS = string.ascii_lowercase + ' '

    def __init__(self, font):
        self.font = ImageFont.truetype(font, 8)
        self.size = 5

    def glyph(self, letter):
        size = self.font.getsize('W')
        image = Image.new('1', size, 1)

        draw = ImageDraw.Draw(image)
        draw.text((0, 0), letter, font=self.font)

        g = [[False] * self.size for _ in range(self.size)]
        index = self.LETTERS.index(letter)

        for row in range(self.size):
            for col in range(self.size):
                if letter == '_':
                    g[row][col] = False
                elif letter == '#':
                    g[row][col] = True
                else:
                    if image.getpixel((col, row)):
                        g[row][col] = False
                    else:
                        g[row][col] = True

        return index, g


class Display:
    DOTS = [
        [0x7223, 0x561d, 0x68db, 0x28d8, 0x7c90],
        [0xf340, 0xf214, 0xa713, 0xc257, 0x5a90],
        [0xbf20, 0x8726, 0xc694, 0xea26, 0xdf48],
        [0x3068, 0x82d8, 0x78fe, 0x38ff, 0xe289],
        [0xcccf, 0x6dff, 0x4088, 0xb979, 0x826c],
    ]

    def __init__(self, network):
        self.font = Font('fonts/5x5_pixel.ttf')
        self.node2dot = {}
        self.dot2node = {}

        for row, line in enumerate(self.DOTS):
            for col, node_id in enumerate(line):
                node = network.shorts[node_id]

                self.node2dot[node.address] = (row, col)
                self.dot2node[(col, row)] = node.address
