import requests

# Example usage
class Node:
    def __init__(self, port):
        self.username = ''
        self.islogin = False
        self.port = port

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
        print(f"{self.username} was trying to log out")
        response = requests.post(url, data={"username": self.username})
        if response.status_code == 200:
            self.islogin = False
            return True
        else:
            return False

    def publish(self, filenames):
        url = "http://127.0.0.1:8000/api/add-filename/"
        addr = "http://127.0.0.1:" + str(self.port)
        payload = {
            "username": self.username, 
            "address": addr, 
            "filenames": filenames
        }
        response = requests.post(url, data=payload)
        print(response)
        if response.status_code == 200:
            print("Added successful")
            return True
        else:
            print("Failed to add filenames")
            return False

    def fetch(self, filemames):
        url = "http://127.0.0.1:8000/api/get-peer-list/"
        addr = "http://127.0.0.1:" + str(self.port)
        payload = {
            "filename": filemames 
        }
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            response = response.json()
            print("Fetched successful")
            return response['peers']
        else:
            print("Failed to fetch peers")
            return []

myport = int(input("Port: "))
myNode = Node(myport)

print("you are running at port " + str(myNode.port))

while True:
    try:
        if myNode.islogin:
            command = input("3.addfileafterlogin 4.logout 5.fetch q.quit: ")
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
                myNode.login_user(user, pwsd)
                if myNode.islogin:
                    print("Login successful")
                else:
                    print("Login failed.")

            case '3':
                filenames = input("Enter files wanted to add: ")
                myNode.publish(filenames)  
            case '4':
                if myNode.logout_user():
                    print("Logout successful")
                else:
                    print("Logout failed.")
            case '5':
                filenames = input("Enter files wanted to fetch: ")
                peerList = myNode.fetch(filenames)
                for p in peerList:
                    print(p)

            case 'q':
                myNode.logout_user()
                print("bye")
                exit()
            case _:
                print("Invalid command. Please try again.")
    except Exception as e:
        print(e)        
            


