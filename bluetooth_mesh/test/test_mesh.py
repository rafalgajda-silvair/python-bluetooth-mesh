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
import uuid

from pytest import fixture, skip, raises

from bluetooth_mesh.crypto import ApplicationKey, DeviceKey, NetworkKey
from bluetooth_mesh.mesh import (SecureNetworkBeacon, AccessMessage, NetworkMessage,
                                 SegmentAckMessage, ControlMessage, Nonce,
                                 UnprovisionedDeviceBeacon)

@fixture
def app_key():
    return ApplicationKey(bytes.fromhex('63964771734fbd76e3b40519d1d94a48'))


@fixture
def net_key():
    return NetworkKey(bytes.fromhex('7dd7364cd842ad18c17c2b820c84c3d6'))


@fixture
def dev_key():
    return DeviceKey(bytes.fromhex('9d6dd0e96eb25dc19a40ed9914f8f03f'))


@fixture
def health_current_status_message():
    payload = bytes.fromhex('0400000000')
    return AccessMessage(src=0x1201, dst=0xffff, ttl=0x03, payload=payload)


@fixture
def config_appkey_status_message():
    payload = bytes.fromhex('800300563412')
    return AccessMessage(src=0x1201, dst=0x0003, ttl=0x0b, payload=payload)


@fixture
def config_appkey_add_message():
    payload = bytes.fromhex('0056341263964771734fbd76e3b40519d1d94a48')
    return AccessMessage(src=0x0003, dst=0x1201, ttl=0x04, payload=payload)


@fixture
def control_appkey_add_ack_message():
    return SegmentAckMessage(src=0x2345, dst=0x0003, ttl=0x0b, seq_zero=0x09ab, ack_segments=[1], obo=True)


@fixture
def control_friend_offer_message():
    parameters = bytes.fromhex('320308ba072f')
    return ControlMessage(src=0x2345, dst=0x1201, ttl=0x00, opcode=0x04, payload=parameters)


def test_network_beacon_received(net_key):
    beacon, auth = SecureNetworkBeacon.unpack(bytes.fromhex('003ecaff672f673370123456788ea261582f364f6f'))

    assert beacon.verify(auth, net_key)

    assert beacon.network_id == net_key.network_id
    assert not beacon.key_refresh
    assert not beacon.iv_update
    assert beacon.iv_index == 0x12345678


def test_network_beacon_received_iv_update(net_key):
    beacon, auth = SecureNetworkBeacon.unpack(bytes.fromhex('023ecaff672f67337012345679c2af80ad072a135c'))

    assert beacon.verify(auth, net_key)

    assert beacon.network_id == net_key.network_id
    assert not beacon.key_refresh
    assert beacon.iv_update
    assert beacon.iv_index == 0x12345679


def test_network_beacon_created(net_key):
    beacon = SecureNetworkBeacon(False, False, 0x12345678, network_id=net_key.network_id)

    assert beacon.pack(net_key) == (bytes.fromhex('003ecaff672f67337012345678'),
                                    bytes.fromhex('8ea261582f364f6f'))


def test_unprovisioned_beacon_received():
    beacon = UnprovisionedDeviceBeacon.unpack(bytes.fromhex('25bdf2eb03cc4383a65add3e8007fb554243'))

    assert beacon.uuid == uuid.UUID('25bdf2eb-03cc-4383-a65a-dd3e8007fb55')
    assert beacon.oob == 0x4243


def test_unprovisioned_beacon_received_uri_hash():
    beacon = UnprovisionedDeviceBeacon.unpack(bytes.fromhex('25bdf2eb03cc4383a65add3e8007fb55424301020304'))

    assert beacon.uuid == uuid.UUID('25bdf2eb-03cc-4383-a65a-dd3e8007fb55')
    assert beacon.oob == 0x4243
    assert beacon.uri_hash == bytes.fromhex('01020304')


def test_unprovisioned_beacon_received_uri_hash_too_short():
    with raises(ValueError, match='expected 4 bytes'):
        UnprovisionedDeviceBeacon.unpack(bytes.fromhex('25bdf2eb03cc4383a65add3e8007fb554243010203'))


def test_unprovisioned_beacon_created():
    beacon = UnprovisionedDeviceBeacon(uuid.UUID('25bdf2eb-03cc-4383-a65a-dd3e8007fb55'),
                                       0x4243)

    assert beacon.pack() == bytes.fromhex('25bdf2eb03cc4383a65add3e8007fb554243')


def test_unprovisioned_beacon_created_uri_hash():
    beacon = UnprovisionedDeviceBeacon(uuid.UUID('25bdf2eb-03cc-4383-a65a-dd3e8007fb55'),
                                       0x4243,
                                       bytes.fromhex('04030201'))

    assert beacon.pack() == bytes.fromhex('25bdf2eb03cc4383a65add3e8007fb55424304030201')

def test_unprovisioned_beacon_created_uri_hash_too_short():
    with raises(ValueError, match='expected 4 bytes'):
        beacon = UnprovisionedDeviceBeacon(uuid.UUID('25bdf2eb-03cc-4383-a65a-dd3e8007fb55'),
                                           0x4243,
                                           bytes.fromhex('040302'))


def test_network_nonce(config_appkey_status_message):
    assert Nonce(config_appkey_status_message.src,
                 config_appkey_status_message.dst,
                 config_appkey_status_message.ttl,
                 False).network(seq=0x000006, iv_index=0x12345678) == bytes.fromhex('000b0000061201000012345678')


def test_device_nonce(config_appkey_status_message):
    assert Nonce(config_appkey_status_message.src,
                 config_appkey_status_message.dst,
                 config_appkey_status_message.ttl,
                 False).device(seq=0x000006, iv_index=0x12345678) == bytes.fromhex('02000000061201000312345678')


def test_application_nonce(health_current_status_message):
    assert Nonce(health_current_status_message.src,
                 health_current_status_message.dst,
                 health_current_status_message.ttl,
                 False).application(seq=0x000007, iv_index=0x12345678) == bytes.fromhex('01000000071201ffff12345678')


def test_device_pdu(config_appkey_status_message, dev_key):
    segment, = \
        config_appkey_status_message.segments(dev_key, seq=0x000006, iv_index=0x12345678)

    assert segment == bytes.fromhex('0089511bf1d1a81c11dcef')


def test_application_pdu(health_current_status_message, app_key):
    segment, = \
        health_current_status_message.segments(app_key, seq=0x000007, iv_index=0x12345678)

    assert segment == bytes.fromhex('665a8bde6d9106ea078a')


def test_application_pdu_segmented(config_appkey_add_message, dev_key):
    segments = list(config_appkey_add_message.segments(dev_key, seq=0x3129ab,
                                                       iv_index=0x12345678))

    assert segments[0] == bytes.fromhex('8026ac01ee9dddfd2169326d23f3afdf')
    assert segments[1] == bytes.fromhex('8026ac21cfdc18c52fdef772e0e17308')


def test_application_network_pdu(health_current_status_message, app_key, net_key):
    network_message = NetworkMessage(health_current_status_message)

    (seq, network_pdu), = \
        network_message.pack(app_key, net_key, seq=0x000007, iv_index=0x12345678)

    assert network_pdu.hex() == '6848cba437860e5673728a627fb938535508e21a6baf57'


def test_application_network_pdu_segmented_retry(health_current_status_message, app_key, net_key):
    network_message = NetworkMessage(health_current_status_message)

    (seq, network_pdu), = \
        network_message.pack(app_key, net_key, seq=0x000017, iv_index=0x12345678,
                             transport_seq=0x000007)

    assert seq == 0x000017
    assert network_pdu.hex() == '6860f30170e2192e84fb4385254e9e71657aa1bcf2ca90'


def test_control_segment_ack_message(control_appkey_add_ack_message, app_key, net_key):
    network_message = NetworkMessage(control_appkey_add_ack_message)

    (seq, network_pdu), = \
        network_message.pack(app_key, net_key, seq=0x014835, iv_index=0x12345678)

    assert network_pdu.hex() == '68e476b5579c980d0d730f94d7f3509df987bb417eb7c05f'


def test_control_message(control_friend_offer_message, app_key, net_key):
    network_message = NetworkMessage(control_friend_offer_message)

    (seq, network_pdu), = \
        network_message.pack(app_key, net_key, seq=0x014820, iv_index=0x12345678)

    assert network_pdu.hex() == '68d4c826296d7979d7dbc0c9b4d43eebec129d20a620d01e'
