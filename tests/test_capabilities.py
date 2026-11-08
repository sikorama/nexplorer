from nexplorer.capabilities import MINIMUM_DOT, capabilities


def test_a_current_dot_supports_everything():
    c = capabilities("5.9.14")
    assert c.rename and c.copy and c.crc and c.free_space


def test_a_dot_older_than_5_9_2_has_no_crc_but_keeps_copy():
    c = capabilities("5.9.1")
    assert not c.crc and c.copy and c.free_space


def test_a_dot_older_than_5_2_has_no_copy_nor_free_space():
    c = capabilities("5.1.3")
    assert not c.copy and not c.free_space and not c.crc


def test_versions_compare_numerically_not_as_text():
    assert capabilities("5.10.0").crc
    assert capabilities("5.9.2").crc


def test_an_unparseable_version_proves_nothing_missing():
    for text in ("", "garbage", "5.x", "v5.9"):
        c = capabilities(text)
        assert c.rename and c.copy and c.crc and c.free_space


def test_a_dot_that_cannot_answer_y_is_older_than_5_8_so_it_has_no_crc():
    c = capabilities(None)
    assert not c.crc and c.copy and c.rename


def test_minimum_version_is_the_one_in_the_protocol_reference():
    assert MINIMUM_DOT == "5.9.2"
