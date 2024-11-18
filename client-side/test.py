# built-in libraries
import struct
import threading
from utils import *
import argparse
from threading import Lock, Thread, Timer
from operator import itemgetter
import datetime
import time
from itertools import groupby
import mmap
import warnings
import json
import ast
warnings.filterwarnings("ignore")
import requests
from client.torrent_parser import TorrentParser
# implemented classes
from configs import CFG, Config
config = Config.from_json(CFG)
from messages.message import Message
from messages.node2tracker import Node2Tracker
from messages.node2node import Node2Node
from messages.chunk_sharing import ChunkSharing
from segment import TCPSegment
import tkinter as tk
import os
import random
from http.client import responses
from tkinter import messagebox
from client.trackerRequest import TrackerClient
next_call = time.time()
FORMAT ="utf-8"
update_bitfield =Lock()

class myGUI:
    def __init__(self):
        self.my_address = ''
        self.root = tk.Tk()
        self.root.title("Client")
        tk.Label(self.root, text="Server's address:").grid(row=0, column=0, padx=10, pady=5, sticky="e")

        self.tracker_entry = tk.Entry(self.root)
        self.tracker_entry.grid(row=0, column=1, padx=10, pady=5)
        self.tracker_entry.insert(0, "127.0.0.1:6969")  # Default value

        # file entry
        tk.Label(self.root, text="enter file name:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.torrent_entry = tk.Entry(self.root)
        self.torrent_entry.grid(row=1, column=1, padx=10, pady=5)

        # Response box for displaying tracker response
        self.response_text = tk.StringVar()
        self.response_box = tk.Text(self.root, height=8, width=40, wrap="word")
        self.response_box.grid(row=2, column=0, columnspan=2, padx=10, pady=5)
        self.response_box.insert("1.0", "You are connecting to 127.0.0.1:6969\n")
        self.response_box.config(state="disabled")

        # Buttons for upload, download, and showing .torrent files
        self.button_frame = tk.Frame(self.root)
        self.button_frame.grid(row=3, column=0, columnspan=2, pady=10)

        self.upload_button = tk.Button(self.button_frame, text="Upload", command=self.upload_torrent)
        self.upload_button.grid(row=0, column=0, padx=5)

        self.download_button = tk.Button(self.button_frame, text="Download", command=self.download_torrent)
        self.download_button.grid(row=0, column=1, padx=5)

        self.show_button = tk.Button(self.button_frame, text="Show .torrent files", command=self.show_torrents)
        self.show_button.grid(row=0, column=2, padx=5)

        self.connect_button = tk.Button(self.root, text="Connect to Tracker", command=lambda: self.update_response(self.connect_tracker()))
        self.connect_button.grid(row=4, column=0, columnspan=2, pady=10)

        # Run the Tkinter main loop
        self.root.mainloop()

    def connect_tracker(self):
        if self.my_address != "":
            self.update_response(f"Ur already connected with the addr of {self.my_address}...")
        else:
            tracker_addr = self.tracker_entry.get()
            rand = random.randint(10000, 99999)
            self.my_address = str('127.0.0.1:' + str(rand))
            # Placeholder response for connecting to the tracker
            self.update_response(f"Attempting to connect to tracker at {tracker_addr} with the address of {self.my_address}...")

    def upload_torrent(self):
        file_name = self.torrent_entry.get()
        if not file_name.endswith('.torrent'):
            file_name += '.torrent'
        self.update_response(f"Uploading {file_name}")

    def download_torrent(self):
        # torretnt -setMode download <filename.torrent>
        file_name = self.torrent_entry.get()
        if not file_name.endswith('.torrent'):
            file_name += '.torrent'

        command = "torretnt -setMode download", file_name
        self.update_response(f"{command}")

    def show_torrents(self):
        folder = 'files'
        files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]

        print(files)
        for file in files:
            self.update_response(file)
        # response_text.set("Show .torrent files functionality not yet implemented.\n")

    def update_response(self, text):
        self.response_box.config(state="normal")
        # response_box.delete("1.0", "end")  # Clear previous text

        self.response_box.insert("1.0", "\n")
        self.response_box.insert("1.0", text)
        # response_box.insert("1.0", "\nYou are having:")
        self.response_box.config(state="disabled")

    # Example call to `update_response` on connection

# 

next_call = time.time()
FORMAT ="utf-8"
update_bitfield =Lock()

class Node:
    def __init__(self, node_id: int, port: int, node_ip: str):
        self.send_socket = set_socket(port, node_ip)
        self.connection = False
        self.node_id = node_id
        self.node_ip = node_ip
        self.port = port
        self.files = self.fetch_owned_files()   #---
        self.is_in_send_mode = False    # is thread uploading a file or not
        self.downloaded_files = {}
        self.shared_file_lock = Lock()
        self.swarm_lock =Lock()
        
    def send_segment(self, sock: socket.socket, data: bytes, addr: tuple):
        
        segment = TCPSegment(src_addr=(self.node_ip,self.port),
                             dest_addr=addr,
                             data=data)
        encrypted_data = segment.data
        try:
           sock.connect(segment.dest_addr)
           sock.sendall(encrypted_data)
        except (socket.timeout, socket.error) as e:
            sock.close()

    def create_bitfield_message(self,bitfield_pieces, total_pieces):
        bitfield_payload = b''
        piece_byte = 0
        bit_index = 0
    
        for i in range(total_pieces):
            if i in bitfield_pieces:
                # Set the appropriate bit in piece_byte for this piece
                piece_byte |= (1 << (7 - bit_index))
        
            bit_index += 1

            # If we have filled a byte (8 bits), pack it and reset
            if bit_index == 8:
                bitfield_payload += struct.pack("!B", piece_byte)
                piece_byte = 0
                bit_index = 0

        # If there are remaining bits that didn't complete a byte, pack them
        if bit_index > 0:
            bitfield_payload += struct.pack("!B", piece_byte)

        return bitfield_payload

    def extract_pieces(self,payload):
        bitfield_pieces = set([])
        # for every bytes value in payload check for its bits
        i = 0 
        for byte_value in (payload):
            for j in range(8):
                # check if jth bit is set
                if((byte_value >> j) & 1):
                    piece_number = i * 8 + 7 - j
                    bitfield_pieces.add(piece_number)
            i= i+1 
        # return the extracted bitfield pieces
        return bitfield_pieces
    def update_bitfield_count(self, bitfield_pieces,bitfield_pieces_count,piece_count):
        for piece in bitfield_pieces :
            if piece in bitfield_pieces_count.keys():
                bitfield_pieces_count[piece] += 1
            else:
                bitfield_pieces_count[piece] = 1
        
    def rarest_pieces_first(self,bitfield_pieces_count):
        # check if bitfields are recieved else wait for some time
        while(len(bitfield_pieces_count) == 0):
            time.sleep(5)
        # get the rarest count of the pieces
        rarest_piece_count = min(bitfield_pieces_count.values())
        # find all the pieces with the rarest piece
        rarest_pieces = [piece for piece in bitfield_pieces_count if 
                         bitfield_pieces_count[piece] == rarest_piece_count] 
        # shuffle among the random pieces 
        random.shuffle(rarest_pieces)
        # rarest pieces
        return rarest_pieces[:4]
    def have_piece(self, piece_index, filename ):
        target_bitfiled = None
        print("self.files-------------------->",self.files)
        print("filename--------------------->",filename)
        for f in self.files:
            if f["filename"] == filename:
               target_bitfiled = self.extract_pieces(f["bitfield_pieces"])
               break
        print("target_bitfiled------------------------>",target_bitfiled)
        if piece_index in target_bitfiled:
            return True
        else:
            return False
    def piece_selection_startergy(self,bitfield_pieces_count):
        return self.rarest_pieces_first(bitfield_pieces_count)
    def download_possible(self):
        # socket connection still active to recieve/send
        if not self.connection:
            return False
        # all conditions satisfied 
        return True
     #def download_block(self, piece_index, block_offset, block_length):
        # create a request message for given piece index and block offset
        request_message = request(piece_index, block_offset, block_length)
        # send request message to peer
        self.send_message(request_message)
        
        # torrent statistics starting the timer
        self.torrent.statistics.start_time()
        # recieve response message and handle the response
        response_message = self.handle_response()
        # torrent statistics stopping the timer
        self.torrent.statistics.stop_time()
        
        # if the message recieved was a piece message
        if not response_message or response_message.message_id != PIECE:
            return None
        # validate if correct response is recieved for the piece message
        if not self.validate_request_piece_messages(request_message, response_message):
            return None

        # update the torrent statistics for downloading
        self.torrent.statistics.update_download_rate(piece_index, block_length)

        # successfully downloaded and validated block of piece
        return response_message.block
    def download_piece(self,piece_index,peer_index,piece_length,bitfield_pieces_count, filename, file_path,file_size,to_be_used_owners:list):
        # if not self.have_piece(piece_index,peer_index) or not self.download_possible():
        #     return False
        max_block_length = 16 * (2**10)
        # recieved piece data from the peer
        recieved_piece = b''  
        # block offset for downloading the piece
        block_offset = 0
        # block length 
        block_length = 0
        noChunk =False
        noConnection =False
        # piece length for torrent 
        # piece_length = self.torrent.get_piece_length(piece_index)
        bitfile_count = file_size // piece_length
        if piece_index < bitfile_count:
            t_piece_length = piece_length
        else:
            t_piece_length = file_size - piece_index * piece_length
        # loop untill you download all the blocks in the piece
        while block_offset < t_piece_length:
            # find out how much max length of block that can be requested
            if t_piece_length - block_offset >= max_block_length:
                block_length = max_block_length
            else:
                block_length = t_piece_length - block_offset
            range = (piece_index, block_offset, block_length)
            block_data = self.receive_chunk(filename, range ,peer_index,bitfield_pieces_count,file_path, piece_length,to_be_used_owners)
            if block_data:
                # increament offset according to size of data block recieved
                recieved_piece += block_data
                block_offset   += block_length
            elif block_data == -1: 
                noConnection = True
                return
            else:
                noChunk= True
        if noConnection:
            if peer_index in to_be_used_owners:
                self.swarm_lock.acquire()
                to_be_used_owners.remove(peer_index)
                self.swarm_lock.release()
            return 
        if noChunk:
            return
        # if block_offset == piece_length:
        self.swarm_lock.acquire()
        # print("bitfield_pieces_count-----------------1--------->",bitfield_pieces_count)
        print("pieces_index-------------------------->",piece_index)
        del bitfield_pieces_count[piece_index]
        self.downloaded_files[filename].append(piece_index)
        self.swarm_lock.release()
        return 

        
        # used for EXCECUTION LOGGING
        
    def move_descriptor_position(self, index_position, file_descriptor):
        os.lseek(file_descriptor, index_position, os.SEEK_SET)

    def read(self,file_descriptor, buffer_size):
        byte_stream = os.read(file_descriptor, buffer_size)
        return byte_stream
    
    def read_block(self, piece_index, block_offset, block_size):
            
        self.shared_file_lock.acquire()
        
        # initialize the file descriptor at given piece index and block offset
        self.initalize_file_descriptor(piece_index, block_offset)
        
        # read the block of data into the file
        data_block  = self.download_file.read(block_size)

        self.shared_file_lock.release()
        
        # return the read block of data
        return data_block
    def write(self,file_descriptor, byte_stream):
        os.write(file_descriptor, byte_stream) 
    def write_block(self, piece_message, file_path, piece_length):
        file_descriptor = os.open(file_path, os.O_RDWR | os.O_CREAT) 
        # extract the piece index, block offset and data recieved from peer  
        # print("piece_message------------->",piece_message)
        piece_index     = piece_message["range"][0]
        block_offset    = piece_message["range"][1]
        data_block      = piece_message["chunk"]
        # self.shared_file_lock.acquire()

        # initialize the file descriptor at given piece index and block offset
        # self.initalize_file_descriptor(piece_index, block_offset)
        
        file_descriptor_position = piece_index * piece_length + block_offset
        self.move_descriptor_position(file_descriptor_position, file_descriptor)
        # write the block of data into the file
        self.write(file_descriptor,data_block)
        # self.shared_file_lock.release()

    def send_chunk(self, filename: str, rng: tuple, dest_node_id: int, dest_port: int,peer_socket, piece_length: int):
        file_path = f"{config.directory.node_files_dir}node{self.node_id}/{filename}"
        file_descriptor = os.open(file_path, os.O_RDWR | os.O_CREAT) 
        # print("piece_length----------------->",piece_length)
        file_descriptor_position = rng[0] * piece_length + rng[1]

        # move the file descripter to the desired location 
        self.move_descriptor_position(file_descriptor_position,file_descriptor)
        # chunk_pieces = self.split_file_to_chunks(file_path=file_path,
        #                                          rng=rng)
        # temp_port = generate_random_port()
        # temp_sock = set_socket(self.port, self.node_ip)
        # for idx, p in enumerate(chunk_pieces):
        #     msg = ChunkSharing(src_node_id=self.node_id,
        #                        dest_node_id=dest_node_id,
        #                        filename=filename,
        #                        range=rng,
        #                        idx=idx,
        #                        chunk=p)
        #     log_content = f"The {idx}/{len(chunk_pieces)} has been sent!"
        #     log(node_id=self.node_id, content=log_content)
        #     # self.send_segment(sock=self.send_socket,
        #     #                   data=Message.encode(msg),
        #     #                   addr=("localhost", dest_port))
        block_data = self.read(file_descriptor, rng[2])
        msg = ChunkSharing(src_node_id=self.node_id,
                               dest_node_id=dest_node_id,
                               filename=filename,
                               range=rng,
                               chunk=block_data)
        peer_socket.sendall(Message.encode(msg))
        # now let's tell the neighboring peer that sending has finished (idx = -1)
        # msg = ChunkSharing(src_node_id=self.node_id,
        #                    dest_node_id=dest_node_id,
        #                    filename=filename,
        #                    range=rng)
        # self.send_segment(sock=self.send_socket,
        #                   data=Message.encode(msg),
        #                   addr=("localhost", dest_port))
        # peer_socket.sendall(Message.encode(msg))
        log_content = "The process of sending a chunk to node{} of file {} has finished!".format(dest_node_id, filename)
        log(node_id=self.node_id, content=log_content)

        # msg = Node2Tracker(node_id=self.node_id,
        #                    mode=config.tracker_requests_mode.UPDATE,
        #                    filename=filename)

        # self.send_segment(sock=self.send_socket,
        #                   data=Message.encode(msg),
        #                   addr=tuple(config.constants.TRACKER_ADDR))

        # free_socket(temp_sock)

    def handle_requests(self, msg: dict, addr: tuple,peer_socket):
        # 1. asks the node about a file size
        if "size" in msg.keys() and msg["size"] == -1:
            self.tell_file_size(msg=msg, addr=addr,peer_socket =peer_socket)
        
        # 2. Wants a chunk of a file
        elif "range" in msg.keys() :
            if not self.have_piece(msg["range"][0], msg["filename"]) :
                msg = ChunkSharing(src_node_id=self.node_id,
                               dest_node_id=msg["src_node_id"],
                               filename=msg["filename"],
                               range=msg["range"],
                               chunk=-1)
                peer_socket.sendall(Message.encode(msg))
            else:
                self.send_chunk(filename=msg["filename"],
                            rng=msg["range"],
                            piece_length = msg["piece_length"],
                            dest_node_id=msg["src_node_id"],
                            dest_port=addr[1],
                            peer_socket =peer_socket)
            print("toi day roi")
        #  đây là dùng để cho hàm discover trong tracker
        # elif "action" in msg.keys() and msg["action"] == 'request_file_list':
        #     response = {'files': self.files}
        #     peer_socket.sendall(json.dumps(response).encode() + b'\n')
        # # dùng cho "ping" cho tracker khi mà muốn ping.
        # elif "action" in msg.keys() and msg["action"] == 'ping':
        #     msg = Node2Tracker(node_id=self.node_id,
        #                        mode=config.tracker_requests_mode.REGISTER,
        #                        filename="")
        #     peer_socket.sendall(Message.encode(msg))
    
    def listen(self):
        self.send_socket.bind((self.node_ip,self.port))
        self.send_socket.listen(5)
        self.connection =True
        while True:
            recieved_connection = self.send_socket.accept()
            if recieved_connection != None:
                peer_socket, peer_address = recieved_connection
                data = peer_socket.recv(config.constants.BUFFER_SIZE)
                msg = Message.decode(data)
                # print("msg::::",msg)
                self.handle_requests(msg=msg, addr=peer_address,peer_socket = peer_socket)

    def set_send_mode(self, filename: str, parser_metadata: object): 
        isInfiles =False
        for file in self.files:
            if filename == file["filename"]:
                isInfiles = True
        if not isInfiles:
            log(node_id=self.node_id,
                content=f"You don't have {filename}")
            return
        bitfield_set = set([])
        pieces_length = 29
        for i in range(pieces_length):
            bitfield_set.add(i)
        # print(bitfield_set)
        bitfield_pieces = self.create_bitfield_message(bitfield_set, pieces_length)
        
        targetFile = {
            "file_name": filename,
            "bitfield_pieces": bitfield_pieces,
            "pieces_length": pieces_length
        }
        print("targetFile-------->",targetFile)
        tracker_url = parser_metadata["tracker_url"] + "/announce"
        params = {
            'info_hash': parser_metadata["info_hash"],
            'fileName': filename,
            'peer_id': str(self.node_id),
            'port': self.port,
            'uploaded': 0,
            'downloaded': 0,
            'left': parser_metadata["total_size"],
            'event': 'started',
            "piece_length": parser_metadata["piece_length"],
        }
        print(f"{tracker_url}?{params}")
        response = requests.get(tracker_url, params=params)

        if response.status_code == 200:
            log_content = f"Tracker response: {response.json()}"
            log(node_id=self.node_id, content=log_content)
        else:
            log_content = f"Tracker response: {response}"
            log(node_id=self.node_id, content=log_content)
            return
        if self.is_in_send_mode:    # has been already in send(upload) mode
            log_content = f"Some other node also requested a file from you! But you are already in SEND(upload) mode!"
            log(node_id=self.node_id, content=log_content)
            return
        else:
            self.is_in_send_mode = True
            log_content = f"You are free now! You are waiting for other nodes' requests!"
            log(node_id=self.node_id, content=log_content)
            t = Thread(target=self.listen, args=())
            t.setDaemon(True)
            t.start()

    def ask_file_size(self, filename: str, peer_index ,bitfield_pieces_count,to_be_used_owners: list) -> int:
        # temp_port = generate_random_port()
        # temp_sock = set_socket(temp_port,self.node_ip)
        # self.send_socket = set_socket(self.port, self.node_ip)
        peer_socket =socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        dest_node = to_be_used_owners[peer_index][0]
        # print(dest_node["addr"][0],dest_node["addr"][1])
        msg = Node2Node(src_node_id=self.node_id,
                        dest_node_id=dest_node["node_id"],
                        filename=filename)
        self.send_segment(sock=peer_socket,
                          data=msg.encode(),
                          addr= (dest_node["addr"][0],dest_node["addr"][1]))
        if peer_socket.fileno() == -1:
            self.swarm_lock.acquire()
            print("Socket is closed.")
            to_be_used_owners.pop(peer_index)
            self.swarm_lock.release()
            return
        while True:
               #dest_node_response = conn.recv(config.constants.BUFFER_SIZE).decode(FORMAT)
               data = peer_socket.recv(config.constants.BUFFER_SIZE)
               dest_node_response = Message.decode(data)
            #    print("dest_node_response-------------->",dest_node_response)
               if dest_node_response is None :
                   to_be_used_owners.pop(peer_index)
                   return
               size = dest_node_response["size"] # co the luu o day la piece_length laf piece_count
               bitfield_pieces = dest_node_response["bitfield_pieces"]
               target_bitfield_pieces = self.extract_pieces(bitfield_pieces)
            #    print("target_bitfield_pieces-------------->",target_bitfield_pieces)
               update_bitfield.acquire()
               self.update_bitfield_count(target_bitfield_pieces, bitfield_pieces_count,dest_node_response["pieces_count"])
               update_bitfield.release() 
               free_socket(peer_socket)
               
               return {
                   "file_size": size,
                   "pieces_count":  dest_node_response["pieces_count"]
               }

    def tell_file_size(self, msg: dict, addr: tuple,peer_socket):
        filename = msg["filename"]
        file_path = f"{config.directory.node_files_dir}node{self.node_id}/{filename}"
        file_size = os.stat(file_path).st_size
        bitfield_pieces = next((item["bitfield_pieces"] for item in self.files if item["filename"] == filename), None)
        pieces_count = next((item["pieces_count"] for item in self.files if item["filename"] == filename), None)
        response_msg = Node2Node(src_node_id=self.node_id,
                        dest_node_id=msg["src_node_id"],
                        filename=filename,
                        size=file_size,
                        bitfield_pieces=bitfield_pieces,
                        pieces_count=pieces_count)
        # temp_port = generate_random_port()
        # temp_sock = set_socket(self.port,self.node_ip)
        # self.send_segment(sock=self.send_socket,
        #                   data=response_msg.encode(),
        #                   addr=addr)
        peer_socket.sendall(response_msg.encode())
        # free_socket(temp_sock)

    def receive_chunk(self, filename: str, range: tuple , peer_index: tuple, bitfield_pieces_count,file_path, piece_length,to_be_used_owners):
        dest_node = peer_index[0]
        # we set idx of ChunkSharing to -1, because we want to tell it that we
        # need the chunk from it
        msg = ChunkSharing(src_node_id=self.node_id,
                           dest_node_id=dest_node["node_id"],
                           filename=filename,
                           range=range,
                           piece_length=piece_length)
        # temp_port = generate_random_port()
        temp_sock = set_socket(self.port,self.node_ip)
        self.send_segment(sock=temp_sock,
                          data=msg.encode(),
                          addr=tuple(dest_node["addr"]))
        log_content = "I sent a request for a chunk of {0} for node{1}".format(filename, dest_node["node_id"])

        log(node_id=self.node_id, content=log_content)
        print("piece_index------------------->",range[0])
        if temp_sock.fileno() == -1:
            self.swarm_lock.acquire()
            print("Socket is closed.")
            to_be_used_owners.pop(peer_index)
            self.swarm_lock.release()
            return False
        while True:
            data = temp_sock.recv(config.constants.BUFFER_SIZE)
            print("data-------------------->",data)
            if data == b'':
                return -1
            msg = Message.decode(data) # but this is not a simple message, it contains chunk's bytes
            if msg["chunk"] == -1:
                return False
            self.shared_file_lock.acquire()
            self.write_block(msg,file_path, piece_length)
            self.shared_file_lock.release()
            free_socket(temp_sock)
            return msg["chunk"]
    
    def sort_downloaded_chunks(self, filename: str) -> list:
        sort_result_by_range = sorted(self.downloaded_files[filename],
                                      key=itemgetter("range"))
        group_by_range = groupby(sort_result_by_range,
                                 key=lambda i: i["range"])
        sorted_downloaded_chunks = []
        for key, value in group_by_range:
            value_sorted_by_idx = sorted(list(value),
                                         key=itemgetter("idx"))
            sorted_downloaded_chunks.append(value_sorted_by_idx)

        return sorted_downloaded_chunks
    def download_complete(self, filename: str, length_count ):
        if filename in self.downloaded_files and len(self.downloaded_files[filename]) == length_count:
            return True
        return False
    def add_entry_to_json(self,node_files_path, filename, bitfield_pieces, pieces_count):
        # node_files_path = 'node_files/' + 'node' + '1' + "/" + "statusFile.json"
        # Step 1: Read existing data from the file, or initialize an empty dictionary if the file doesn't exist
        try:
            with open(node_files_path, 'r') as file:
                data = json.load(file)  # Load existing data
        except FileNotFoundError:
            data = {}
    # Prepare the new entry to be added
        new_entry = {
            str(len(data)+1): {
                "filename": filename,
                "bitfield_pieces": bitfield_pieces,
                "pieces_count": pieces_count
            }
        }

        # Step 2: Add the new entry to the data
        data.update(new_entry)

        # Step 3: Write the updated data back to the file
        with open(node_files_path, 'w') as file:
            json.dump(data, file, indent=4)

        print(f"Added entry for ID {len(data)} to {node_files_path}.")
    def split_file_owners(self, file_owners: list, filename: str,parser_metadata):
        owners = []
        bitfield_pieces_count = dict()
        self.downloaded_files.setdefault(filename, [])
        for owner in file_owners:
            if owner[0]['node_id'] != self.node_id:
                # bitfield_pieces = self.extract_pieces(owner[0]['bitfield_pieces'])
                # owner[0]['bitfield_pieces'] = bitfield_pieces
                owners.append(owner)
        if len(owners) == 0:
            log_content = f"No one has {filename}"
            log(node_id=self.node_id, content=log_content)
            return
        # sort owners based on their sending frequency
        owners = sorted(owners, key=lambda x: x[1], reverse=True)
        # 5 peer parrabell
        to_be_used_owners = owners[:config.constants.MAX_SPLITTNES_RATE]
        # 1. first ask the size of the file from peers
        log_content = f"You are going to download {filename} from Node(s) {[o[0]['node_id'] for o in to_be_used_owners]}"
        log(node_id=self.node_id, content=log_content)
        # print("to_be_used_owners-------------------->",to_be_used_owners)
        
        #target = self.ask_file_size(filename=filename, peer_index= 0 ,bitfield_pieces_count= {}, to_be_used_owners=to_be_used_owners)
        files = parser_metadata["files"]
        piece_length = parser_metadata["piece_length"]
        target_file= None
        for file in files:
            if file["path"]== filename:
                target_file = file
        file_size = target_file["length"]
        
        pieces_count = (file_size // piece_length) + 1
        log_content = f"The file {filename} which you are about to download, has size of {file_size} bytes"
        log(node_id=self.node_id, content=log_content)
        # ask for bitfield and update to count amount of piece
        connect_peer_thread_arr = []
        for peer_index in range(len(to_be_used_owners)):
            connect_peer_thread = Thread(target = self.ask_file_size, args=(filename, peer_index, bitfield_pieces_count, to_be_used_owners))
            connect_peer_thread_arr.append(connect_peer_thread)
            connect_peer_thread.start()
        for t in connect_peer_thread_arr:
            t.join()
        # piece_length = file_size // (pieces_count - 1) # cho  dang custom
        # length_count = len() # ////29
        # ---------------------------> dang toi day
        print("to_be_used_owners-------------------->",to_be_used_owners)
        print("bitfield_pieces_count--------------------->",bitfield_pieces_count) 
        # print("piece_length--------------------------->",piece_length)
        while not self.download_complete(filename, pieces_count):
            file_path = f"{config.directory.node_files_dir}node{self.node_id}/{filename}"
            pieces = self.piece_selection_startergy(bitfield_pieces_count)
            downloading_thread_pool = []
            for i in range(min(len(pieces), len(to_be_used_owners))):
                piece = pieces[i]
                peer_index = to_be_used_owners[i]
                #28
                downloading_thread = Thread(target=self.download_piece, args=(piece, peer_index,piece_length,bitfield_pieces_count,filename,file_path,file_size,to_be_used_owners))
                downloading_thread_pool.append(downloading_thread)
                downloading_thread.start()
            for downloading_thread in downloading_thread_pool:
                downloading_thread.join()
        
        # sẽ ghi lại vào file status tình trạng khi mà đã tải file
        print("download_files------------------------->",self.downloaded_files[filename])     
        # chuyen sang bitfield roif chuyen sang hex ghi vaof laij file status
        # Byte_bitfield = self.create_bitfield_message(self.downloaded_files[filename], pieces_count)

        # node_files_path = config.directory.node_files_dir + 'node' + str(self.node_id) + "/" + "statusFile.json"

        # self.add_entry_to_json(node_files_path,filename,Byte_bitfield.hex(),pieces_count)
        
        #  py node.py -node_id 1 -port 12345 -node_ip "127.0.0.1"
        # file_size = self.ask_file_size(filename=filename, file_owner=to_be_used_owners[0])
        # log_content = f"The file {filename} which you are about to download, has size of {file_size} bytes"
        # log(node_id=self.node_id, content=log_content)
        # print("file_size---------------->",file_size)
        # 2. Now, we know the size, let's split it equally among peers to download chunks of it from them
        # step = file_size / len(to_be_used_owners)
        # chunks_ranges = [(round(step*i), round(step*(i+1))) for i in range(len(to_be_used_owners))]

        log_content = f"{filename} has successfully downloaded and saved in my files directory."
        log(node_id=self.node_id, content=log_content)
        self.files.append(filename)

    def set_download_mode(self, filename: str, parser_metadata):
        file_path = f"{config.directory.node_files_dir}node{self.node_id}/{filename}"
        if os.path.isfile(file_path):
            log_content = f"You already have this file!"
            log(node_id=self.node_id, content=log_content)
            return
        else:
            log_content = f"You just started to download {filename}. Let's search it in torrent!"
            log(node_id=self.node_id, content=log_content)
            # tracker_response = self.search_torrent(filename=filename)
            # file_owners = tracker_response['search_result']
            # client = TrackerClient(
            #     id=self.node_id,
            #     port=self.port,
            #     info_hash_hex=parser_metadata['info_hash'],
            #     total_length=parser_metadata['total_size'],
            # )

            # file_owners = client.get_peers(parser_metadata["tracker_url"])
            tracker_url = parser_metadata["tracker_url"] + "/searchFiles"
            params = {
                'info_hash': parser_metadata["info_hash"],
                'fileName': filename,
                'peer_id': str(self.node_id),
                'port': self.port,
                'uploaded': 0,
                'downloaded': 0,
                'left': parser_metadata["total_size"],
                'event': 'started',
                "piece_length": parser_metadata["piece_length"],
            }
            print(f"{tracker_url}?{params}")
            response = requests.get(tracker_url, params=params)
            print(response.json())
            if response.status_code == 200:
                log_content = f"Tracker response: {response.json()}"
                log(node_id=self.node_id, content=log_content)
            else:
                log_content = f"Tracker response: {response}"
                log(node_id=self.node_id, content=log_content)
                return
            if not file_owners:
                log_content = f"Sorry, no one has {filename}!"
                log(node_id=self.node_id, content=log_content)
                return
            print("file_owners------------------>",file_owners)
            file_owners = [
                ({"node_id": 1, 
                 "addr": ["127.0.0.1", 12345],
                },2),
                ({"node_id": 2, 
                 "addr": ["127.0.0.1", 12346],
                },2)
            ]
            # self.split_file_owners(file_owners=file_owners, filename=filename, parser_metadata= parser_metadata)

    def fetch_owned_files(self) -> list:
        files = []
        node_files_path = config.directory.node_files_dir + 'node' + str(self.node_id) + "/" + "statusFile.json"
        with open(node_files_path, 'r') as file:
            data = json.load(file)
        for file_id, file_data in data.items():
            filename = file_data['filename']
            # Use `ast.literal_eval` to convert the byte string safely
            bitfield_set = set([])
            piece_count = file_data['pieces_count']
            for i in range(piece_count):
                bitfield_set.add(i)
        # print(bitfield_set)
            bitfield_pieces = self.create_bitfield_message(bitfield_set, piece_count)
            # bitfield = byte_format = bytes.fromhex(bitfield_hex)
            # pieces_count = file_data['pieces_count']
            # Display the result
            target_file = {
                "fileId": file_id,
                "filename": filename,
                "bitfield_pieces":bitfield_pieces,
                "pieces_count": piece_count
            }
            files.append(target_file)
        print("specific_files::::",files)
        return files



def run(args):
    node = Node(node_id=args.node_id,
                port=args.port,
                node_ip= args.node_ip)
    
    log_content = f"***************** Node program started just right now! *****************"
    log(node_id=node.node_id, content=log_content)

    print("ENTER YOUR COMMAND!")
    while True:
        command = input()
        mode, filenames_0 = parse_command(command)
        
        parser = TorrentParser(filenames_0[0])
        parser_metadata = parser.get_metadata()
        print("parser_metadata----------------->",parser_metadata)
        filenames = [file['path'] for file in parser_metadata['files']]
        print("filenames----------------->",filenames)
        #################### send mode ####################
        if mode == 'send':
            # node.set_send_mode(filename=filename)
            threads = []
            for filename in filenames:
                thread = threading.Thread(target=node.set_send_mode, args=(filename,parser_metadata))
                threads.append(thread)
                thread.start()
            for thread in threads:
                thread.join() 
        #################### download mode ####################
        elif mode == 'download':
            # t = Thread(target=node.set_download_mode, args=(filename,))
            # t.setDaemon(True)
            # t.start()
            threads = []
            for filename in filenames:
                thread = threading.Thread(target=node.set_download_mode, args=(filename,filenames_0[0]))
                threads.append(thread)
                thread.start()
            for thread in threads:
                thread.join()    
        #################### exit mode ####################
        elif mode == 'exit':
            # node.exit_torrent()
            free_socket(node.send_socket)
            node.connection =False
            exit(0)

def getFileOwners():
    ffile_owners = [
            ({"node_id": 1, 
                "addr": ["127.0.0.1", 12345],
            },2),
            ({"node_id": 2, 
                "addr": ["127.0.0.1", 12346],
            },2)
        ]
    return ffile_owners
#----------------------------------------------------------------
# HTTP APIs service
def login_user():
    # body = {
    #     "username": entry_username.get(), 
    #     "password": entry_password.get(),
    #     "address": my_address, 
    # }
    # print(body)
    url = "http://127.0.0.1:6969/login/"
    body = {
        "username": entry_username.get(),
        "password": entry_password.get()
    }
    headers = {"Content-Type": "application/json"}  # Set the content type to JSON


    response = requests.get(url, headers=headers, json=body)
    return response


def handleLogin():
    # response = login_user()
    # print(response) 
    islogin = True
    login_frame.pack_forget()
    register_frame.pack_forget()
    window.title(f"BiK-Torrent - [{my_id}]")
    main_frame.pack()




def handleRegister():
    if rlabel_password_again.get() == rlabel_password.get():
        pass

    pass

def get_available_files():
    url = "http://127.0.0.1:8000/api/torrents"
    headers = {
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        # Raise an error or return None if there was an issue
        response.raise_for_status()
        return None

#----------------------------------------------------------------
def upload_torrent():
    file_name = torrent_entry.get()
    if not file_name.endswith('.torrent'):
        file_name += '.torrent'

    # file_name = "SE_file.torrent"
    parser = TorrentParser(file_name)
    parser_metadata = parser.get_metadata()

    filenames = [file['path'] for file in parser_metadata['files']]
    for f in filenames:
        update_response(f)
        
    update_response("-----------------")
    update_response("Filenames")

    print("parser_metadata----------------->",parser_metadata)
    update_response(f"total_size {parser_metadata['total_size']}")
    update_response(f"piece_count {parser_metadata['piece_count']}")
    update_response(f"piece_length {parser_metadata['piece_length']}")
    update_response(f"tracker_url {parser_metadata['tracker_url']}")
    update_response(f"info_hash {parser_metadata['info_hash']}")
    update_response("File Info")
    update_response("---------------")

    threads = []
    for filename in filenames:
        thread = threading.Thread(target=node.set_send_mode, args=(filename,parser_metadata))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join() 


    update_response(f"Uploading {file_name}")

def download_torrent():
    

    file_name = torrent_entry.get()
    if not file_name.endswith('.torrent'):
        file_name += '.torrent'

    # file_name = "SE_file.torrent"
    parser = TorrentParser(file_name)
    parser_metadata = parser.get_metadata()

    filenames = [file['path'] for file in parser_metadata['files']]
    for f in filenames:
        update_response(f)
        
    update_response("-----------------")
    update_response("Filenames")

    print("parser_metadata----------------->",parser_metadata)
    update_response(f"total_size {parser_metadata['total_size']}")
    update_response(f"piece_count {parser_metadata['piece_count']}")
    update_response(f"piece_length {parser_metadata['piece_length']}")
    update_response(f"tracker_url {parser_metadata['tracker_url']}")
    update_response(f"info_hash {parser_metadata['info_hash']}")
    update_response("File Info")
    update_response("---------------")

    threads = []
    for filename in filenames:
        thread = threading.Thread(target=node.set_download_mode, args=(filename,parser_metadata)) # [0]: [1]: local .torrent file
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()    

    peer_list = getFileOwners()
    # for p in peer_list:
    #     update_response(p["addr"])

    update_response(f"Downloading {file_name}")
    
def show_whoami():
    update_response(f"[{my_id}] I am {my_address}")


def handleExit():
    pass
def exit_program():
    handleExit()
    window.destroy()

def show_torrents():
    folder = 'torrent_files'
    files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]

    for file in files:
        update_response(file)
    update_response("-----Your .torrent files-----")

def show_files():
    for f in node.files:
        update_response(f"[f{f['fileId']}] {f['filename']} | piece count: {f['pieces_count']}")
    update_response("-----Your files in local storage-----")

def show_available():
    # response = get_available_files()
    # print(requests)
    # for f in avail_files:
    #     update_response(f)
    update_response("-----      On development      -----")
    update_response("-----Available torrent in Swarm-----")
def update_response(text):
    response_box.config(state="normal")
    # response_box.delete("1.0", "end")  # Clear previous text

    response_box.insert("1.0", f"{text}\n")
    # response_box.insert("1.0", "\nYou are having:")
    response_box.config(state="disabled")

def changeToRegister():
    login_frame.pack_forget()
    register_frame.pack()
def changeToLogin():
    register_frame.pack_forget()
    login_frame.pack()

def himom():
    # update_response("Hi mom!")
    response_box.config(state="normal")

# Clear the content
    response_box.delete("1.0", "end")

    # Optionally disable it again to make it read-only
    response_box.config(state="disabled")

def on_closing():
    if messagebox.askyesno(title="Quit?", message="Do you want to quit?"):
        exit_program()
        
if __name__ == '__main__':

    # my_port = random.randint(5000, 9999)
    my_port = int(input("Enter port: "))
    my_address = "127.0.0.1:" + str(my_port)
    my_id = int(input("Enter your desired id: "))

    node_args2 = argparse.Namespace(node_id=my_id, port=my_port, node_ip="127.0.0.1")

    node = Node(node_id=my_id,
                port=my_port,
                node_ip="127.0.0.1")


    print(node_args2)


    islogin = False

    window = tk.Tk()
    window.title("BiK-Torrent - Login")
    window.geometry("600x400")

    login_frame = tk.Frame(window)
    register_frame = tk.Frame(window)
    main_frame = tk.Frame(window)
    main_frame.rowconfigure(2, weight=1)  # Allow row 2 to expand
    main_frame.columnconfigure(0, weight=1)  # Allow column 0 to expand
    main_frame.columnconfigure(1, weight=1)  # Allow column 1 to expand

    login_frame.pack(fill="both", expand=True)
    label_username = tk.Label(login_frame, text="Username")
    label_username.pack(pady=5)
    entry_username = tk.Entry(login_frame)
    entry_username.pack(pady=5)

    label_password = tk.Label(login_frame, text="Password")
    label_password.pack(pady=5)
    entry_password = tk.Entry(login_frame, show="*")
    entry_password.pack(pady=5)

    login_button = tk.Button(login_frame, text="Login", command=handleLogin)
    login_button.pack(pady=10)

    to_register_button = tk.Button(login_frame, text="to Register", command=changeToRegister)
    to_register_button.pack(pady=10)
    #----------------

    rlabel_username = tk.Label(register_frame, text="Username")
    rlabel_username.pack(pady=5)
    rentry_username = tk.Entry(register_frame)
    rentry_username.pack(pady=5)

    rlabel_password = tk.Label(register_frame, text="Password")
    rlabel_password.pack(pady=5)
    rentry_password = tk.Entry(register_frame, show="*")
    rentry_password.pack(pady=5)

    rlabel_password_again = tk.Label(register_frame, text="Password (again)")
    rlabel_password_again.pack(pady=5)
    rlabel_password_again = tk.Entry(register_frame, show="*")
    rlabel_password_again.pack(pady=5)

    register_button = tk.Button(register_frame, text="Register", command=handleRegister)
    register_button.pack(pady=10)

    to_login_button = tk.Button(register_frame, text="to Login", command=changeToLogin)
    to_login_button.pack(pady=10)
    # --------------------------------------------------

    tk.Label(main_frame, text="Server's address:").grid(row=0, column=0, padx=10, pady=5, sticky="e")
    tracker_entry = tk.Entry(main_frame)
    tracker_entry.grid(row=0, column=1, padx=10, pady=5)
    tracker_entry.insert(0, "127.0.0.1:6969")  # Default value


    # file entry
    tk.Label(main_frame, text="Enter a file name:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
    torrent_entry = tk.Entry(main_frame)
    torrent_entry.grid(row=1, column=1, padx=10, pady=5)


    # Response box for displaying tracker response
    response_text = tk.StringVar()
    response_box = tk.Text(main_frame, height=50, width=100, wrap="word")
    response_box.grid(row=2, column=0, columnspan=2, padx=10, pady=5)
    response_box.insert("1.0", f"You are connecting to {tracker_entry.get()}\n")
    response_box.config(state="disabled")


    # Buttons for upload, download, and showing .torrent files
    button_frame = tk.Frame(main_frame)
    button_frame.grid(row=3, column=0, columnspan=2, pady=10)

    upload_button = tk.Button(button_frame, text="Upload", command=upload_torrent)
    upload_button.grid(row=0, column=2, padx=5, sticky=tk.W+tk.E)

    download_button = tk.Button(button_frame, text="Download", command=download_torrent)
    download_button.grid(row=0, column=1, padx=5, sticky=tk.W+tk.E)

    exit_button = tk.Button(button_frame, text="Exit", command=exit_program)
    exit_button.grid(row=0, column=0, padx=5, sticky=tk.W+tk.E)

    whoami_button = tk.Button(button_frame, text="whoami", command=show_whoami)
    whoami_button.grid(row=1, column=0, padx=5, sticky=tk.W+tk.E)

    show_button = tk.Button(button_frame, text="Show .torrent files", command=show_torrents)
    show_button.grid(row=1, column=1, padx=5, sticky=tk.W+tk.E)

    show_f_button = tk.Button(button_frame, text="Show local files", command=show_files)
    show_f_button.grid(row=1, column=2, padx=5, sticky=tk.W+tk.E)

    hi_mom_button = tk.Button(button_frame, text="Hi mom!", command=himom)
    hi_mom_button.grid(row=2, column=0, padx=5, sticky=tk.W+tk.E)

    show_available_button = tk.Button(button_frame, text="Show torrents in swarm", command=show_available)
    show_available_button.grid(row=2, column=1, columnspan=3, padx=5, sticky=tk.W+tk.E)

    # connect_button = tk.Button(main_frame, text="Connect to Tracker", command=lambda: self.update_response(self.connect_tracker()))
    # connect_button.grid(row=4, column=0, columnspan=2, pady=10)





    # --------------------------------------------------



    window.protocol("WM_DELETE_WINDOW", on_closing)
    window.mainloop()


