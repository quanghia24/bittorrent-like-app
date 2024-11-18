import requests
import urllib.parse
import struct
import random
import string
import socket
from typing import List, Tuple
import bencodepy
from typing import Dict, Any
import json

class TrackerClient:
    """Client for communicating with BitTorrent trackers and discovering peers."""
    
    def __init__(self, id: int, port: int, info_hash_hex: str, total_length: int):
        """
        Initialize tracker client.
        
        Args:
            info_hash_hex: Torrent info hash in hexadecimal format
            total_length: Total length of files in torrent
            port: Port number client is listening on
        """
        self.info_hash_bytes = info_hash_hex
        self.peer_id = id
        self.port = port
        self.uploaded = 0
        self.downloaded = 0
        self.left = total_length
        
    @staticmethod
    def _generate_peer_id() -> bytes:
        """Generate a unique 20-byte peer ID."""
        # Use standard convention: '-PC0001-' followed by 12 random chars
        prefix = "-PC0001-"
        random_chars = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        return (prefix + random_chars).encode()
    
    def get_peers(self, tracker_url: str) -> List[Tuple[str, int]]:
        """
        Get list of peers from tracker.
        
        Args:
            tracker_url: URL of the tracker
            
        Returns:
            List of (ip, port) tuples for available peers
            
        Raises:
            RequestError: If tracker request fails
            ValueError: If tracker response is invalid
        """
        try:
            response = self._make_tracker_request(tracker_url)
            
            #Parse response from tracker
            response_json = response.json()
            print(response_json)
            peers = response_json.get('peers', [])
            return [(peer['ip'], peer['port']) for peer in peers]
        except requests.RequestException as e:
            raise RequestError(f"Tracker request failed: {str(e)}")
        except (KeyError, struct.error) as e:
            raise ValueError(f"Invalid tracker response: {str(e)}")
    
    def _make_tracker_request(self, tracker_url: str) -> Dict[bytes, Any]:
        """Make GET request to tracker with required parameters."""
        params = {
            'info_hash': self.info_hash_bytes,
            'peer_id': self.peer_id,
            'port': self.port,
            'uploaded': self.uploaded,
            'downloaded': self.downloaded,
            'left': self.left,
            # 'compact': 1
        }
        
        # Construct URL with properly encoded parameters
        query_string = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        full_url = f"{tracker_url}/announce?{query_string}"
        
        response = requests.get(full_url)
        response.raise_for_status()
        
        return response
    
    @staticmethod
    def _parse_compact_peers(peers_data: bytes) -> List[Tuple[str, int]]:
        """
        Parse compact peer data into list of (ip, port) tuples.
        
        The compact peer format uses 6 bytes per peer:
        - 4 bytes for IP address
        - 2 bytes for port number
        """
        peers = []
        for i in range(0, len(peers_data), 6):
            peer_data = peers_data[i:i+6]
            if len(peer_data) < 6:
                continue
                
            # Unpack IP (4 bytes) and port (2 bytes)
            ip_bytes = peer_data[:4]
            port_bytes = peer_data[4:6]
            
            # Convert IP bytes to string representation
            ip = socket.inet_ntoa(ip_bytes)
            # Convert port bytes to integer (network byte order)
            port = struct.unpack("!H", port_bytes)[0]
            
            peers.append((ip, port))
            
        return peers

class RequestError(Exception):
    """Raised when tracker request fails."""
    pass