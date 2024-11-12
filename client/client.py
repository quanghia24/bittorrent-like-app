from typing import Optional, Dict
from urllib.parse import urlencode
import requests
import time
import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path

# Add project root to Python path to enable imports
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

from torrent_parser import TorrentParser
from config.settings import CLIENT_CONFIG

@dataclass
class TorrentMetadata:
    info_hash: str
    piece_length: int
    total_length: int
    piece_count: int
    name: str
    tracker_url: str
    
    @classmethod
    def from_parser(cls, parser_metadata: Dict) -> 'TorrentMetadata':
        """Create TorrentMetadata from parser output"""
        return cls(
            info_hash=parser_metadata['info_hash'],
            piece_length=parser_metadata['piece_length'],
            total_length=parser_metadata['total_size'],  # Match parser's output
            piece_count=parser_metadata['piece_count'],
            name=parser_metadata['name'],
            tracker_url=parser_metadata['tracker_url']
        )

class PeerAnnouncer:
    def __init__(self, tracker_url: str, peer_id: str, 
                 port: int = CLIENT_CONFIG['default_port']):
        self.tracker_url = tracker_url
        self.peer_id = peer_id
        self.port = port
        self.active_torrents: Dict[str, TorrentMetadata] = {}
        
    def add_torrent(self, metadata: TorrentMetadata):
        """Register a new torrent that this peer is sharing"""
        self.active_torrents[metadata.info_hash] = metadata
        print(f"Added torrent: {metadata.name} ({metadata.info_hash})")
        
    def announce(self, info_hash: str, event: str = '', uploaded: int = 0, 
                downloaded: int = 0, left: int = 0) -> Optional[dict]:
        """
        Announce this peer's status to the tracker
        
        Args:
            info_hash: Hash of the torrent info dictionary
            event: Optional event ('started', 'completed', 'stopped')
            uploaded: Total number of bytes uploaded
            downloaded: Total number of bytes downloaded
            left: Number of bytes left to download
            
        Returns:
            Dictionary containing peer list and announce interval if successful
        """
        if info_hash not in self.active_torrents:
            print(f"Error: Torrent {info_hash} not registered")
            return None
            
        metadata = self.active_torrents[info_hash]
        params = {
            'info_hash': info_hash,
            'peer_id': self.peer_id,
            'port': self.port,
            'uploaded': uploaded,
            'downloaded': downloaded,
            'left': left if left > 0 else metadata.total_length,
            'event': event
        }
        
        try:
            # Construct announce URL with parameters
            announce_url = f"{metadata.tracker_url}/announce?{urlencode(params)}"
            
            print(f"Announcing to: {announce_url}")
            
            # Make announcement request
            response = requests.get(announce_url, timeout=30)
            response.raise_for_status()
            
            response_data = response.json()
            print(f"Received response: {len(response_data.get('peers', []))} peers")
            return response_data
            
        except requests.exceptions.RequestException as e:
            print(f"Announcement failed: {str(e)}")
            return None
            
    def start_announcing(self, info_hash: str, interval: int = 1800):
        """
        Start periodic announcements for a torrent
        
        Args:
            info_hash: Hash of the torrent to announce
            interval: Time between announcements in seconds
        """
        if info_hash not in self.active_torrents:
            print(f"Error: Torrent {info_hash} not registered")
            return
            
        print(f"Starting announcements for {self.active_torrents[info_hash].name}")
        
        try:
            # First announcement with 'started' event
            response = self.announce(info_hash, event='started')
            
            if not response:
                print("Initial announcement failed")
                return
                
            while True:
                time.sleep(interval)
                response = self.announce(info_hash)
                
                if response:
                    # Update interval if tracker suggests a different one
                    interval = response.get('interval', interval)
                    print(f"Next announcement in {interval} seconds")
                else:
                    print("Announcement failed, using default interval")
                    
        except KeyboardInterrupt:
            print("\nStopping announcements...")
            self.stop_announcing(info_hash)
            
    def stop_announcing(self, info_hash: str):
        """Stop announcing a torrent and notify tracker"""
        if info_hash in self.active_torrents:
            print(f"Stopping announcements for {self.active_torrents[info_hash].name}")
            self.announce(info_hash, event='stopped')
            del self.active_torrents[info_hash]

def main(torrent_file: str):
    """
    Main function to start announcing a torrent
    
    Args:
        torrent_file: Path to the .torrent file
    """
    try:
        # Parse the torrent file
        parser = TorrentParser(torrent_file)
        parser_metadata = parser.get_metadata()
        print("parser_metadata----------------->",parser_metadata)
        # Convert to our metadata format
        metadata = TorrentMetadata.from_parser(parser_metadata)
        
        # Generate a random peer ID
        peer_id = hashlib.sha1(os.urandom(20)).hexdigest()[:20]
        
        # Create announcer instance
        announcer = PeerAnnouncer(
            tracker_url=metadata.tracker_url,
            peer_id=peer_id
        )
        
        # Register and start announcing the torrent
        # announcer.add_torrent(metadata)
        # announcer.start_announcing(metadata.info_hash)
        
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python -m client.announce <torrent_file>")
        print("sys.argv------------->",sys.argv)
        sys.exit(1)
    main(sys.argv[1])