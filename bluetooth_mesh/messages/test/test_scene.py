import pytest
from construct import SelectError, ValidationError

from bluetooth_mesh.messages.scene import SceneMessageOpcode, SceneMessage

invalid = [
    pytest.param(
        SelectError,
        SceneMessageOpcode.SCENE_RECALL,
        dict(scene_number=0, tid=30),
        id="SCENE_RECALL_minimal_with_prohibited_scene_number"),
    pytest.param(
        SelectError,
        SceneMessageOpcode.SCENE_RECALL,
        dict(scene_number=0, tid=30, transition_time=30000, delay=0.3),
        id="SCENE_RECALL_with_transition_with_prohibited_scene_number"),
    pytest.param(
        SelectError,
        SceneMessageOpcode.SCENE_RECALL_UNACKNOWLEDGED,
        dict(scene_number=0, tid=30),
        id="SCENE_RECALL_UNACKNOWLEDGED_minimal_with_prohibited_scene_number"),
    pytest.param(
        SelectError,
        SceneMessageOpcode.SCENE_RECALL_UNACKNOWLEDGED,
        dict(scene_number=0, tid=30, transition_time=30000, delay=0.3),
        id="SCENE_RECALL_UNACKNOWLEDGED_with_transition_with_prohibited_scene_number"),
    pytest.param(
        ValidationError,
        SceneMessageOpcode.SCENE_STORE,
        dict(scene_number=0),
        id="SCENE_STORE_with_prohibited_scene_number"),
    pytest.param(
        ValidationError,
        SceneMessageOpcode.SCENE_STORE_UNACKNOWLEDGED,
        dict(scene_number=0),
        id="SCENE_STORE_UNACKNOWLEDGED_with_prohibited_scene_number")
]

valid = [
    pytest.param(
        b'\x82\x41',
        SceneMessageOpcode.SCENE_GET,
        dict(),
        id="SCENE_GET"),
    pytest.param(
        b'\x82\x42\x01\x00\x1e',
        SceneMessageOpcode.SCENE_RECALL,
        dict(scene_number=1, tid=30),
        id="SCENE_RECALL_minimal"),
    pytest.param(
        b'\x82\x43\x01\x00\x1e',
        SceneMessageOpcode.SCENE_RECALL_UNACKNOWLEDGED,
        dict(scene_number=1, tid=30),
        id="SCENE_RECALL_UNACKNOWLEDGED_minimal"),
    pytest.param(
        b'\x82\x42\x01\x00\x1e\xf2\x3c',
        SceneMessageOpcode.SCENE_RECALL,
        dict(scene_number=1, tid=30, transition_time=30000, delay=0.3),
        id="SCENE_RECALL_with_transition"),
    pytest.param(
        b'\x82\x43\x01\x00\x1e\xf2\x3c',
        SceneMessageOpcode.SCENE_RECALL_UNACKNOWLEDGED,
        dict(scene_number=1, tid=30, transition_time=30000, delay=0.3),
        id="SCENE_RECALL_UNACKNOWLEDGED_with_transition"),
    pytest.param(
        b'\x5e\x00\x01\x00',
        SceneMessageOpcode.SCENE_STATUS,
        dict(status_code=0, current_scene=1),
        id="SCENE_STATUS_minimal"),
    pytest.param(
        b'\x5e\x00\x01\x00\x02\x00\xf2',
        SceneMessageOpcode.SCENE_STATUS,
        dict(status_code=0, current_scene=1, target_scene=2, remaining_time=30000),
        id="SCENE_STATUS_with_target_scene"),
    pytest.param(
        b'\x82\x44',
        SceneMessageOpcode.SCENE_REGISTER_GET,
        dict(),
        id="SCENE_REGISTER_GET"),
    pytest.param(
        b'\x82\x45\x00\x01\x00\x01\x00\x02\x00' + 14 * b'\x00\x00',
        SceneMessageOpcode.SCENE_REGISTER_STATUS,
        dict(status_code=0, current_scene=1, scenes=[1, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
        id="SCENE_REGISTER_STATUS"),
    pytest.param(
        b'\x82\x46\x01\x00',
        SceneMessageOpcode.SCENE_STORE,
        dict(scene_number=1),
        id="SCENE_STORE"),
    pytest.param(
        b'\x82\x47\x01\x00',
        SceneMessageOpcode.SCENE_STORE_UNACKNOWLEDGED,
        dict(scene_number=1),
        id="SCENE_STORE_UNACKNOWLEDGED"),
    pytest.param(
        b'\x82\x9e\x01\x00',
        SceneMessageOpcode.SCENE_DELETE,
        dict(scene_number=1),
        id="SCENE_DELETE"),
    pytest.param(
        b'\x82\x9f\x01\x00',
        SceneMessageOpcode.SCENE_DELETE_UNACKNOWLEDGED,
        dict(scene_number=1),
        id="SCENE_DELETE_UNACKNOWLEDGED"),
]


@pytest.mark.parametrize("encoded,opcode,data", valid)
def test_parse_valid(encoded, opcode, data):
    assert SceneMessage.parse(encoded).params == data


@pytest.mark.parametrize("encoded,opcode,data", valid)
def test_build_valid(encoded, opcode, data):
    assert SceneMessage.build(dict(opcode=opcode, params=data)) == encoded


@pytest.mark.parametrize("exception,opcode,data", invalid)
def test_build_valid(exception,opcode, data):
    with pytest.raises(exception):
        SceneMessage.build(dict(opcode=opcode, params=data))
