import requests
from torrentParser import *
from threading import *
import time
# Example usage




class Node:
    def __init__(self, port):
        self.username = ''
        self.islogin = False
        self.port = port
        self.hasTorrent = False

    def create_user(self, username, password):
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

    def publish(self, file):
        self.hasTorrent = True
        url = "http://127.0.0.1:8000/api/add-filename/"
        addr = "http://127.0.0.1:" + str(self.port)
        # get file
        # debencode
        parser = TorrentParser(filepath=file)
        metadata = parser.get_metadata()

        # metadata = {
        #     'info_hash': self.info_hash,
        #     'tracker_url': self.data[b'announce'].decode(),
        #     'piece_length': self.info_dict[b'piece length'],
        #     'private': bool(self.info_dict.get(b'private', 0)),
        #     'name': self.info_dict[b'name'].decode(),
        #     'files': self.get_files(),
        #     'total_size': sum(f['length'] for f in self.get_files()),
        #     'piece_count': len(self.get_piece_hashes()),
        # }

        payload = {
            "username": self.username, 
            "address": addr, 
            "name": file,
            "info_hash": metadata['info_hash'],
            "piece_length": metadata['piece_length'],
            "filenames": metadata['files']
        }

        print(payload)

        response = requests.post(url, json=payload)
        print(response)
        if response.status_code == 200:
            print(response.json())
            print("Added successful")
            return True
        else:
            print("Failed to add filenames")
            return False

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
                    files = filenames.split()
                    print("Your trying to add files", files)
                    for file in files:
                        myNode.publish(file)  

                case '4':
                    filenames = input("Enter file you wanted to fetch: ")
                    peerList = myNode.fetch(filenames)
                    for p in peerList:
                        print(p)

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
        print()
        print(f"{myNode.username} was trying to stay alive")
        if myNode.send_heartbeat():
            print("you have sent a heartbeat")
        else:
            print("failed to send heartbeat")
        time.sleep(15)

if __name__ == "__main__":
    myport = int(input("Port: "))
    myNode = Node(myport)

    T = Thread(target=keep_alive)
    T.daemon = True
    T.start()

    main_task()

              

