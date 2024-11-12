from configs import CFG, Config
config = Config.from_json(CFG)

class TCPSegment:
    def __init__(self, src_addr: tuple, dest_addr: tuple, data: bytes):
        # TCP
        assert len(data) <= config.constants.MAX_TCP_SEGMENT_DATA_SIZE, print(
            f"MAXIMUM DATA SIZE OF A UDP SEGMENT IS {config.constants.MAX_TCP_SEGMENT_DATA_SIZE}"
        )
        self.src_addr = src_addr
        self.dest_addr = dest_addr
        self.length = len(data)
        self.data = data


