from typing import Any, Dict, List
import hashlib
from pathlib import Path
import bencodepy

class TorrentParser:
    """A class to handle parsing and analysis of torrent files."""
    
    def __init__(self, filepath: str = None, raw_data: bytes = None):
        """Initialize parser with either a file path or raw torrent data."""
        if filepath and raw_data:
            raise ValueError("Specify either filepath or raw_data, not both")
        self.data = None
        if filepath:
            self._load_from_file(filepath)
        elif raw_data:
            self._load_from_bytes(raw_data)
    
    
    def _load_from_file(self, filepath: str) -> None:
        """Load and parse torrent data from a file."""
        filepath = "torrent_files/" + filepath
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Torrent file not found: {filepath}")
        with open(filepath, 'rb') as f:
            self._load_from_bytes(f.read())
    
    def _load_from_bytes(self, data: bytes) -> None:
        """Parse raw torrent data."""
        try:
            self.data = bencodepy.decode(data)
            self.info_dict = self.data[b'info']
            self.info_hash = hashlib.sha1(bencodepy.encode(self.info_dict)).hexdigest()
        except Exception as e:
            raise ValueError(f"Failed to parse torrent data: {str(e)}")
    
    def get_piece_hashes(self) -> List[str]:
        """Extract and return list of piece hashes."""
        pieces = self.info_dict[b'pieces']
        return [pieces[i:i+20].hex() for i in range(0, len(pieces), 20)]
    
    def get_files(self) -> List[Dict[str, Any]]:
        """Get file information for single or multi-file torrents."""
        if b'files' in self.info_dict:
            # Multi-file torrent
            return [{
                'path': '/'.join(p.decode() for p in f[b'path']),
                'length': f[b'length']
            } for f in self.info_dict[b'files']]
        else:
            # Single file torrent
            return [{
                'path': self.info_dict[b'name'].decode(),
                'length': self.info_dict[b'length']
            }]
    
    def get_metadata(self) -> Dict[str, Any]:
        """Return comprehensive torrent metadata."""
        metadata = {
            'info_hash': self.info_hash,
            'tracker_url': self.data[b'announce'].decode(),
            'piece_length': self.info_dict[b'piece length'],
            'private': bool(self.info_dict.get(b'private', 0)),
            'name': self.info_dict[b'name'].decode(),
            'files': self.get_files(),
            'total_size': sum(f['length'] for f in self.get_files()),
            'piece_count': len(self.get_piece_hashes()),
        }
        
        # Add optional fields if present
        if b'comment' in self.data:
            metadata['comment'] = self.data[b'comment'].decode()
        if b'created by' in self.data:
            metadata['created_by'] = self.data[b'created by'].decode()
        if b'creation date' in self.data:
            metadata['creation_date'] = self.data[b'creation date']
        
        return metadata