import pytest

from streamers import chunk_streamer


@pytest.mark.parametrize(
    ("chunks", "threshold", "expected"),
    [
        ([], 4, []),
        ([b"", b""], 4, []),
        ([b"ab", b"c"], 4, [b"abc"]),
        ([b"ab", b"cd"], 4, [b"abcd"]),
        ([b"abc", b"def"], 4, [b"abcdef"]),
        ([b"abcdefgh"], 4, [b"abcdefgh"]),
        ([b"ab", b"cd", b"e"], 4, [b"abcd", b"e"]),
        ([b"ab", b"cd", b"ef"], 2, [b"ab", b"cd", b"ef"]),
        ([b"", b"ab", b"", b"cd", b""], 4, [b"abcd"]),
    ],
)
def test_chunk_streamer_output(chunks, threshold, expected):
    result = list(chunk_streamer(iter(chunks), threshold))

    assert all(isinstance(chunk, memoryview) for chunk in result)
    assert all(chunk.readonly for chunk in result)
    assert [bytes(chunk) for chunk in result] == expected


@pytest.mark.parametrize("threshold", [0, -1])
def test_chunk_streamer_rejects_nonpositive_threshold(threshold):
    with pytest.raises(ValueError, match="Chunk threshold must be positive"):
        list(chunk_streamer([], threshold))


def test_chunk_streamer_is_lazy_and_preserves_previous_views():
    consumed = []

    def source():
        for chunk in (b"ab", b"cd", b"ef"):
            consumed.append(chunk)
            yield chunk

    stream = chunk_streamer(source(), threshold=4)
    assert consumed == []

    first = next(stream)
    assert bytes(first) == b"abcd"
    assert consumed == [b"ab", b"cd"]

    assert [bytes(chunk) for chunk in stream] == [b"ef"]
    assert bytes(first) == b"abcd"
