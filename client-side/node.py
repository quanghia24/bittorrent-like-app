import requests
from torrentParser import *
from threading import *
import struct
import threading
from utils import *
import argparse
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
# Example usage

next_call = time.time()
FORMAT ="utf-8"
update_bitfield =Lock()


class Node:

    def __init__(self, port, nid):
        self.username = ''
        self.islogin = False
        self.port = port
        self.hasTorrent = False
        self.node_id = nid
        self.node_ip = "127.0.0.1"
        # ------------
        self.send_socket = set_socket(port, "127.0.0.1")
        self.connection = False
        self.is_in_send_mode = False
        self.downloaded_files = {}
        self.shared_file_lock = Lock()
        self.files = self.fetch_owned_files()
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
    def download_piece(self, piece_index, peer_index, piece_length, bitfield_pieces_count, filename, file_path, file_size, to_be_used_owners:list):
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
    def set_send_mode(self, filename): 
        self.files = self.fetch_owned_files()

        print(f"set_send_mode received {filename}")

        print(self.files)
        print("-------------")
        isInfiles =False
        for file in self.files:

            print(file["filename"])
            if filename == file["filename"]:
                isInfiles = True

        if not isInfiles:
            log(node_id=self.node_id,
                content=f"You don't have {filename}")
            return
        
        response = self.publish(filename)

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
        Byte_bitfield = self.create_bitfield_message(self.downloaded_files[filename], pieces_count)

        node_files_path = config.directory.node_files_dir + 'node' + str(self.node_id) + "/" + "statusFile.json"

        self.add_entry_to_json(node_files_path, filename, self.downloaded_files[filename], pieces_count)

        
        
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

        target_file = {
            "fileId": random.randint(10, 150),
            "filename": filename,
            "bitfield_pieces": self.downloaded_files[filename], 
            "pieces_count": pieces_count
        }
        self.files.append(target_file)


    def set_download_mode(self, filename: str, peerList, metadata):
        file_path = f"{config.directory.node_files_dir}node{self.node_id}/{filename}"
        if os.path.isfile(file_path):
            log_content = f"You already have this file!"
            log(node_id=self.node_id, content=log_content)
            return
        else:
            log_content = f"You just started to download {filename}. Let's search it in torrent!"
            log(node_id=self.node_id, content=log_content)


            if not peerList:
                log_content = f"Sorry, no one has {filename}!"
                log(node_id=self.node_id, content=log_content)
                return
            print("peerList------------------>",peerList)

            # file_owners = [
            #     ({"node_id": 1, 
            #      "addr": ["127.0.0.1", 12345],
            #     },2),
            #     ({"node_id": 2, 
            #      "addr": ["127.0.0.1", 12346],
            #     },2)
            # ]

            self.split_file_owners(file_owners=peerList, filename=filename, parser_metadata= metadata)


    # def fetch_owned_files(self) -> list:
    #     files = []
    #     node_files_path = config.directory.node_files_dir + 'node' + str(self.node_id) + "/" + "statusFile.json"
    #     with open(node_files_path, 'r') as file:
    #         data = json.load(file)
    #     for file_id, file_data in data.items():
    #         filename = file_data['filename']
    #         # Use `ast.literal_eval` to convert the byte string safely
    #         bitfield_set = set([])
    #         piece_count = file_data['pieces_count']
    #         for i in range(piece_count):
    #             bitfield_set.add(i)
    #     # print(bitfield_set)
    #         bitfield_pieces = self.create_bitfield_message(bitfield_set, piece_count)
    #         # bitfield = byte_format = bytes.fromhex(bitfield_hex)
    #         # pieces_count = file_data['pieces_count']
    #         # Display the result
    #         target_file = {
    #             "fileId": file_id,
    #             "filename": filename,
    #             "bitfield_pieces":bitfield_pieces,
    #             "pieces_count": piece_count
    #         }
    #         files.append(target_file)
    #     print("specific_files::::",files)
    #     return files
    def fetch_owned_files(self) -> list:
        files = []
        node_files_path = config.directory.node_files_dir + 'node' + str(self.node_id) + "/" + "statusFile.json"
        with open(node_files_path, 'r') as file:
            data = json.load(file)
        for file_id, file_data in data.items():
            filename = file_data['filename']
            # Use `ast.literal_eval` to convert the byte string safely
            bitfield_hex = file_data['bitfield_pieces'] 
            pieces_count = file_data['pieces_count']
            bitfield_hex_1= set(bitfield_hex)
            traget_bitfield_hex_1= self.create_bitfield_message(bitfield_hex_1, pieces_count)
            # bitfield = byte_format = bytes.fromhex(bitfield_hex)
           
            # Display the result
            target_file = {
                "fileId": file_id,
                "filename": filename,
                "bitfield_pieces":traget_bitfield_hex_1,
                "pieces_count": pieces_count
            }
            files.append(target_file)
        print("specific_files::::",files)
        return files
    # --------------- to tracker ---------------
    def create_user(self, username, password):
        # frontend <-> backend 
        # json
        # api -> http
        url = "http://127.0.0.1:8000/api/create-user/"  # Replace with your backend URL
        payload = {
            "username": username,
            "password": password
        }
        

        try:
            response = requests.post(url, json=payload)
            response_data = response.json()

            if response.status_code == 201:
                print("User created successfully:", response_data)
            else:
                print("Error creating user:", response_data)

        except requests.exceptions.RequestException as e:
            print("An error occurred:", e)
    def login_user(self, username, password):
        url = "http://127.0.0.1:8000/api/login-user/"
        response = requests.post(url, data={"username": username, "password": password})
        if response.status_code == 200:
            self.username = username
            self.islogin = True
            return True
        else:
            return False
    def logout_user(self):
        url = "http://127.0.0.1:8000/api/logout-user/"
        # print(f"{self.username} was trying to log out")
        response = requests.post(url, data={"username": self.username})
        if response.status_code == 200:
            self.islogin = False
            return True
        else:
            return False
    def publish(self, file): # torrent 
        self.hasTorrent = True
        url = "http://127.0.0.1:8000/api/add-filename/"
        addr = "http://127.0.0.1:" + str(self.port)
        # get file
        # debencode
        parser = TorrentParser(filepath=file)
        metadata = parser.get_metadata()
        filenames = [file['path'] for file in metadata['files']]


        payload = {
            "username": self.username, 
            "address": addr, 
            "name": file,
            "info_hash": metadata['info_hash'],
            "piece_length": metadata['piece_length'],
            "filenames": metadata['files'],
            "node_id": self.node_id
        }
        print(payload)

        response = requests.post(url, json=payload)
        print(response)
        return response

        # if response.status_code == 200:
        #     print(response.json())
        #     print("Added successful")
        #     # open a port to listen for requests
        #     for filename in filenames:
        #         T = Thread(target=self.set_send_mode, args=(filename, ))
        #         T.daemon = True
        #         T.start()
        #     print(f"{self.port} is listening")
        #     return True
        # else:
        #     print("Failed to add filenames")
        #     return False
        
    def fetch(self, filemames):
        url = "http://127.0.0.1:8000/api/get-peer-list/"

        parser = TorrentParser(filepath=filemames)
        metadata = parser.get_metadata()

        payload = {
            "info_hash": metadata['info_hash']
        }
        response = requests.post(url, json=payload)

        if response.status_code == 200:
            response = response.json()
            print("Fetched successful")
            return response['peers']
        else:
            print("Failed to fetch peers")
            return []
        
    def send_heartbeat(self):
        if self.hasTorrent == False:
            return False
        
        url = "http://127.0.0.1:8000/api/heartbeat/"
        addr = "http://127.0.0.1:" + str(self.port)

        payload = {
            "username": self.username
        }
        requests.post(url, json=payload)

        return True;

def main_task():
    print("you are running at port " + str(myNode.port))
    while True:
        try:
            if myNode.islogin:
                command = input("3.publish  4.fetch q.quit: ")
            else:
                command = input("1.register 2.login q.quit: ")
            match command:
                case '1':
                    user = input("Enter your username: ")
                    pwsd = input("Password: ")
                    myNode.create_user(user, pwsd)
                case '2':
                    user = input("Enter your username: ")
                    pwsd = input("Password: ")
                    myNode.logout_user()
                    myNode.login_user(user, pwsd)
                    if myNode.islogin:
                        print("Login successful")
                        
                    else:
                        print("Login failed.")

                case '3':
                    filenames = input("Enter files you wanted to publish: ")
                    filenames = filenames.split()
                    print("Your trying to add files", filenames)
                    threads = []
                    for f in filenames:
                        print(f"send {f}")
                        thread = threading.Thread(target=myNode.set_send_mode, args=(f,))
                        threads.append(thread)
                        thread.start()
                    for thread in threads:
                        thread.join()

                case '4':
                    filenames = input("Enter file you wanted to fetch: ")
                    peerList = myNode.fetch(filenames)
                    peerList = list(map(tuple, peerList))
                    print(peerList)

                    for p in peerList:
                        print(p)

                    parser = TorrentParser(filepath=filenames)
                    metadata = parser.get_metadata()

                    print(metadata)

                    files = [file['path'] for file in metadata['files']]

                    threads = []
                    for file in files:
                        thread = threading.Thread(target=myNode.set_download_mode, args=(file, peerList, metadata,))
                        threads.append(thread)
                        thread.start()
                    for thread in threads:
                        thread.join()    
                    
                    node_files_path = config.directory.node_files_dir + 'node' + str(myNode.node_id) + "/" + "statusFile.json"
                    myNode.add_entry_to_json(node_files_path, filenames, [], 0)
                    target_file = {
                        "fileId": random.randint(10,100),
                        "filename": filenames,
                        "bitfield_pieces": [],
                        "pieces_count": 0
                    }
                    myNode.files.append(target_file)
                    print("Hereeeeeeeeeeeeeeeee")
                    print(myNode.files)

                case '6':
                    print("You just updated your frequency")

                case 'q':
                    myNode.logout_user()
                    print("bye")
                    break
                case _:
                    print("Invalid command. Please try again.")
        except Exception as e:
            print(e)

def keep_alive():
    while True:
        if myNode.send_heartbeat():
            print("you have sent a heartbeat")
        # else:
        #     print("failed to send heartbeat")
        time.sleep(15)


if __name__ == "__main__":
    myport = int(input("Port: "))
    myid = int(input("Id: "))
    myNode = Node(myport, myid)

    T = Thread(target=keep_alive)
    T.daemon = True
    T.start()

    main_task()

              

