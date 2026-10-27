from typing import Iterable, Iterator


def chunk_streamer(chunks: Iterable[bytes], threshold: int) -> Iterator[memoryview]:
    """Yield read-only buffers once a positive byte threshold is reached.

    Input chunks stay whole; the final buffer may be smaller than the threshold.
    """
    if threshold <= 0:
        raise ValueError("Chunk threshold must be positive")

    buffer = bytearray()
    for chunk in chunks:
        buffer.extend(chunk)
        if len(buffer) >= threshold:
            yield memoryview(buffer).toreadonly()
            buffer = bytearray()

    if buffer:
        yield memoryview(buffer).toreadonly()
