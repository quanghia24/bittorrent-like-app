from messages.message import Message

class ChunkSharing(Message):
    def __init__(self, src_node_id: int, dest_node_id: int, filename: str,
                 range: tuple, chunk: bytes = None,piece_length: int= -1):

        super().__init__()
        self.src_node_id = src_node_id
        self.dest_node_id = dest_node_id
        self.filename = filename
        self.range = range
        self.piece_length = piece_length
        self.chunk = chunk
