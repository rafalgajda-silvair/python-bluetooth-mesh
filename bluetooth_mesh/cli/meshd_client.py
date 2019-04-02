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
import asyncio
import logging
import os
import re
import traceback
import uuid

from itertools import cycle

import bitstring
import ravel

from docopt import docopt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.eventloop import use_asyncio_event_loop
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit import PromptSession

from bluetooth_mesh.schema import NetworkSchema
from bluetooth_mesh.cli.display import Display, Font


class MeshdClient:
    NODE_PATH = re.compile(r'/org/bluez/mesh/node_(?P<uuid>[0-9a-f_]+)')

    def __init__(self):
        self.bus = ravel.system_bus()
        self.bus.attach_asyncio(asyncio.get_event_loop())
        self.meshd = self.bus['org.bluez.mesh']
        self.object_manager = None
        self.network = None

    async def __aenter__(self):
        self.object_manager = \
            await self.meshd['/'].get_async_interface(
                'org.freedesktop.DBus.ObjectManager')

        self.network = \
            await self.meshd['/org/bluez/mesh'].get_async_interface(
                'org.bluez.mesh.Network1')

    async def __aexit__(self, *args, **kwargs):
        pass

    @classmethod
    def node_path_to_uuid(cls, node_path):
        match = cls.NODE_PATH.match(node_path)
        return uuid.UUID(match.group('uuid').replace('_', '-'))

    @classmethod
    def node_uuid_to_path(cls, node_uuid):
        return '/org/bluez/mesh/node_%s' % str(node_uuid).replace('-', '_')


def needs_node(f):
    async def _wrap(self, *args, **kwargs):
        if self.node is None:
            print('Not attached to any local node')
            return

        return (await f(self, *args, **kwargs))
    return _wrap




class CommandLine:
    def __init__(self, network, client):
        self.network = network
        self.client = client

        self._dir = os.path.expanduser('~/.cache/python-bluetooth-mesh')
        os.makedirs(self._dir, exist_ok=True)
        history = os.path.join(self._dir, 'meshd-client.history')

        self.session = PromptSession(history=FileHistory(history))

        self.tid = cycle(range(255))
        self.display = Display(self.network)
        self.node = None

        self.node_if = None
        self.provisioning_if = None

    @property
    def _commands(self):
        commands = []

        for i in dir(self):
            if i.startswith('cmd_'):
                _, cmd = i.split('cmd_')
                commands.append(cmd)

        return commands

    async def cmd_help(self, _):
        print('\n'.join(map('  {}'.format, self._commands)))

    @property
    def prompt(self):
        if self.node:
            return '%s> ' % self.client.node_path_to_uuid(self.node.path)

        return 'meshd> '

    async def __call__(self):
        async with self.client:
            while True:
                try:
                    command = await self.session.prompt(self.prompt,
                                                        async_=True)
                    command = command.strip()

                    if not command:
                        continue

                    cmd, *argv = command.split(maxsplit=1)

                    future = getattr(self, 'cmd_%s' % cmd, None)

                    if future is None:
                        print("%s: command not found" % cmd)
                        continue

                    await future(argv[0] if argv else '')
                except KeyboardInterrupt:
                    pass
                except EOFError:
                    return
                except Exception:
                    traceback.print_exc()

    async def cmd_network(self, _):
        print('\n'.join('%s %04x' % (i, i.address)
                        for i in self.network.nodes.values()))

    async def cmd_nodes(self, _):
        objects, = await self.client.object_manager.GetManagedObjects()

        for path, interfaces in objects.items():
            if 'org.bluez.mesh.Node1' not in interfaces:
                continue

            provisioning_if = \
                await self.client.meshd[path].get_async_interface(
                    'org.bluez.mesh.Provisioning1')

            provisioned = await provisioning_if.Provisioned

            print(self.client.node_path_to_uuid(path),
                  '(provisioned)' if provisioned else '')

    async def cmd_attach(self, argv):
        node_uuid = uuid.UUID(argv)
        path = '/org/bluez/mesh/node_%s' % (str(node_uuid).replace('-', '_'))
        self.node = self.client.meshd[path]

        self.node_if = \
            await self.node.get_async_interface(
                'org.bluez.mesh.Node1')

        self.provisioning_if = \
            await self.node.get_async_interface(
                'org.bluez.mesh.Provisioning1')

        print('Attached to', self.node.path)

    @needs_node
    async def cmd_detach(self, _):
        print('Detached from', self.node.path)
        self.node = None

    @needs_node
    async def cmd_status(self, _):
        if not await self.provisioning_if.Provisioned:
            print('Not provisioned')
            return

        print('Provisioned')
        print(' - Address:     %04x' % (await self.node_if.Address))
        print(' - Sequence:    %06x' % (await self.node_if.Sequence))
        print(' - Network Key: %s' %
              bytes(await self.node_if.NetworkKey).hex())
        print(' - Device Key:  %s' %
              bytes(await self.node_if.DeviceKey).hex())
        print(' - Application Keys:')

        application_keys = (await self.node_if.ApplicationKeys)

        for index, application_key in application_keys.items():
            print('    %d: %s' % (index, bytes(application_key).hex()))

    @needs_node
    async def cmd_provision(self, argv):
        network_key, address, iv_index = argv.split()
        network_key = bytes.fromhex(network_key)
        address = int(address, 16)
        iv_index = int(iv_index)

        await self.provisioning_if.Provision(list(network_key),
                                             address,
                                             iv_index)

    @needs_node
    async def cmd_unprovision(self, _):
        await self.provisioning_if.Unprovision()

    async def cmd_create(self, _):
        node_uuid = uuid.uuid4()
        await self.client.network.CreateNode(0x0136, 0x0001, 0x0001,
                                             list(node_uuid.bytes),
                                             {})

        print('Created node', node_uuid)

    async def cmd_delete(self, argv):
        node_uuid = uuid.UUID(argv)
        await self.client.network.DeleteNode(list(node_uuid.bytes))

        print('Deleted node', node_uuid)

    async def _send_config(self, opcode, payload):
        await self.node_if.SendMessage(0, (await self.node_if.Address),
                                       list(opcode),
                                       list(payload),
                                       ('q', 0x7fff))

    async def _send_application(self, address, opcode, payload, *, element=0):
        await self.node_if.SendMessage(0, address + element,
                                       list(opcode),
                                       list(payload),
                                       ('q', 0))
        await asyncio.sleep(0.5)

    async def _send_device(self, address, opcode, payload, *, element=0):
        device_key = self.network.device_keys[address]

        print('%04x -> %04x: %s %s' % (await self.node_if.Address,
                                       address + element,
                                       opcode.hex(),
                                       payload.hex()))

        await self.node_if.SendMessage(0, address + element,
                                       list(opcode),
                                       list(payload),
                                       ('ay', list(device_key.bytes)))
        await asyncio.sleep(0.2)

    @needs_node
    async def cmd_attention(self, argv):
        col, row = map(int, argv.split())
        address = self.display.dot2node[(col, row)]
        print('Attention %d, %d: %04x' % (col, row, address))

        await self._send_device(address,
                                bytes.fromhex('8005'),
                                bytes.fromhex('0a'))

    @needs_node
    async def cmd_appkey(self, _):
        for application_key in self.network.application_keys:
            payload = b'\x00\x00\x00' + application_key.bytes

            await self._send_config(bytes.fromhex('00'),
                                    payload)

    @needs_node
    async def cmd_ttl(self, _):
        await self._send_config(bytes.fromhex('800d'),
                                bytes.fromhex('03'))

    @needs_node
    async def cmd_show(self, argv):
        value = 1
        steps = 0
        resolution = 0
        delay = 40

        for letter in argv.replace('_', ' '):
            index, _ = self.display.font.glyph(letter)
            group = 0xd000 + index
            tid = next(self.tid)

            payload = bitstring.pack('uint:8, uint:8, uint:2, uint:6, uint:8',
                                     value, tid, resolution, steps, delay)

            await self._send_application(group,
                                         bytes.fromhex('8203'),
                                         payload.bytes)
            await asyncio.sleep(0.1)

            delay = 20
            payload = bitstring.pack('uint:8, uint:8, uint:2, uint:6, uint:8',
                                     value, tid, resolution, steps, delay)

            await self._send_application(group,
                                         bytes.fromhex('8203'),
                                         payload.bytes)
            await asyncio.sleep(0.1)

    @needs_node
    async def cmd_sequence(self, argv):
        self.node_if.Sequence = int(argv)

    @needs_node
    async def cmd_slow(self, argv):
        steps = 0
        resolution = 0
        delay = 0

        for node in self.network.nodes.values():
            try:
                row, col = self.display.node2dot[node.address]
            except KeyError:
                continue

            for letter in argv.replace('_', ' '):
                _, glyph = self.display.font.glyph(letter)
                value = 1 if glyph[row][col] else 0
                tid = next(self.tid)

                payload = bitstring.pack('uint:8, uint:8, uint:2, uint:6, '
                                         'uint:8',
                                         value, tid, resolution, steps,
                                         delay)

                await self._send_application(node.address,
                                             bytes.fromhex('8203'),
                                             payload.bytes)
                await asyncio.sleep(0.1)

    async def _cmd_onoff(self, argv, onoff):
        col, row = map(int, argv.split())

        address = self.display.dot2node[(col, row)]

        tid = next(self.tid)
        steps = 0
        resolution = 0
        delay = 0

        payload = bitstring.pack('uint:8, uint:8, uint:2, uint:6, uint:8',
                                 onoff, tid, resolution, steps, delay)

        await self._send_application(address,
                                     bytes.fromhex('8203'),
                                     payload.bytes)

    @needs_node
    async def cmd_on(self, argv):
        await self._cmd_onoff(argv, onoff=1)

    @needs_node
    async def cmd_off(self, argv):
        await self._cmd_onoff(argv, onoff=0)

    @needs_node
    async def cmd_unsubscribe(self, _):
        for node in self.network.nodes.values():
            model = 0x1203  # scene server
            payload = bitstring.pack('uintle:16, uintle:16',
                                     node.address + 0, model)

            await self._send_device(node.address,
                                    bytes.fromhex('801d'),
                                    payload.bytes)

            model = 0x1000  # generic on off server
            payload = bitstring.pack('uintle:16, uintle:16',
                                     node.address + 2, model)

            await self._send_device(node.address,
                                    bytes.fromhex('801d'),
                                    payload.bytes)

    @needs_node
    async def cmd_subscribe(self, argv):
        for node in self.network.nodes.values():
            model = 0x1000  # generic on off server

            for letter in argv or Font.LETTERS:
                index, _ = self.display.font.glyph(letter)
                group = 0xd000 + index

                print("Subscribe %04x:%04x to %04x" % (node.address + 2,
                                                       model,
                                                       group))

                payload = bitstring.pack('uintle:16, uintle:16, uintle:16',
                                         node.address + 2, group, model)

                await self._send_device(node.address,
                                        bytes.fromhex('801b'),
                                        payload.bytes)
                await asyncio.sleep(1)

    @needs_node
    async def cmd_untranslate(self, _):
        for node in self.network.nodes.values():
            await self._send_device(node.address,
                                    bytes.fromhex('f83601'),
                                    bytes.fromhex('03'),
                                    element=2)

    @needs_node
    async def cmd_translate(self, argv):
        trigger = 1

        for node in self.network.nodes.values():
            try:
                row, col = self.display.node2dot[node.address]
            except KeyError:
                continue

            for letter in (argv or Font.LETTERS).replace('_', ' '):
                index, glyph = self.display.font.glyph(letter)
                scene = 2 if glyph[row][col] else 1

                group = 0xd000 + index

                payload = bitstring.pack('uintle:16, uint:8, uintle:16',
                                         group, trigger, scene)

                print('Translate %04x:%04x to %04x' % (node.address,
                                                       group,
                                                       scene))

                await self._send_device(node.address,
                                        bytes.fromhex('f83601'),
                                        bytes.fromhex('00') + payload.bytes,
                                        element=2)
                await asyncio.sleep(5)

                return

    @needs_node
    async def cmd_publish(self, _):
        model = 0x1205  # scene client

        steps = 0
        resolution = 0
        ttl = 0
        count = 0
        interval = 1

        for node in self.network.nodes.values():
            payload = bitstring.pack('uintle:16, uintle:16, uint:12, uint:1, '
                                     'pad:3, '
                                     'uint:8, uint:2, uint:6, uint:3, uint:5, '
                                     'uintle:16',
                                     node.address + 2, node.address, 0, 0,
                                     ttl, resolution, steps, count, interval,
                                     model)

            print('Publish %s %04x:%08x to %04x' % (node.uuid,
                                                    node.address + 2,
                                                    model,
                                                    node.address))

            await self._send_device(node.address,
                                    bytes.fromhex('03'),
                                    payload.bytes)
            break
            await asyncio.sleep(1)

    async def cmd_font(self, argv):
        for letter in argv.replace('_', ' '):
            _, glyph = self.display.font.glyph(letter)

            print('\n'.join(''.join('#' if dot else ' ' for dot in row)
                            for row in glyph))


def main(argv=None):
    '''Bluetooth Mesh Client

    Usage:
        gatt-client [options] <network>

    Options:
    '''
    logging.basicConfig(level=logging.DEBUG)

    args = docopt(main.__doc__, argv=argv)

    with open(args['<network>']) as network_file:
        schema = NetworkSchema()
        network = schema.loads(network_file.read())

    client = MeshdClient()

    cli = CommandLine(network, client)

    use_asyncio_event_loop()

    with patch_stdout():
        asyncio.get_event_loop().run_until_complete(cli())
