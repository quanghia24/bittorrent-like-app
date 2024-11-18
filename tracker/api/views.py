from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
import json
from .models import CustomUser, Peer, Torrent
import logging 
from datetime import datetime, timedelta

#now we will Create and configure logger 
# Set up basic logging configuration
logging.basicConfig(
    filename='tracker.log',  # Log file path
    filemode='a',            # Append to the log file
    format='%(asctime)s %(message)s',  # Log message format
    datefmt='%H:%M:%S',      # Time format in the logs
    level=logging.INFO      # Capture all log levels
)

# Get the logger object
logger = logging.getLogger()

# Add custom filter to the logger

User = get_user_model()

@api_view(['POST'])
def announce(request):
    username = request.data.get("username")
    print(f"{username} told that hes still alive")

    if not username:
        return Response({"error": "Missing required fields"}, status=409)

    user = User.objects.get(username=username)
    # Update or create peer entry
    try:
        peers = Peer.objects.filter(user = user)

    except Peer.DoesNotExist:
        return Response({"error": "Failed to update peer"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    for peer in peers:
        peer.update_last_seen()
        peer.save()
    return Response({"message": "Peer updated successfully"})

# def mark_inactive_peers():
#     inactive_time = datetime.now() - timedelta(seconds=10)  # Adjust timeout as needed
#     peers_to_mark = Peer.objects.filter(last_seen__lt=inactive_time, is_active=True)
#     for peer in peers_to_mark:
#         peer.mark_inactive()

@api_view(['POST'])
def get_peers(request):
    info_hash = request.data.get("info_hash")
    torrents = Torrent.objects.filter(info_hash=info_hash)
    file_owners = []
    for torrent in torrents:
        torrent.peer.user.update_freq()
        data = {
            "node_id": torrent.peer.node_id,
            "addr": [
                torrent.peer.address.removeprefix("http://").split(":")[0],  # Extract IP
                int(torrent.peer.address.removeprefix("http://").split(":")[1])  # Extract and convert port to int
            ],
        }
        file_owners.append((data, torrent.peer.user.freq))

    return Response({"peers": file_owners})

@api_view(['POST'])
def create_user(request):
    username = request.data.get("username")
    password = request.data.get("password")


    if not username or not password:
        return Response({"error": "Username and password are required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.create_user(username=username, password=password)
        logger.info(f"Account named [{username}] just got created") 
        return Response({"message": "User created successfully", "username": user.username}, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def login_user(request):
    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        return Response({"error": "Username and password are required"}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.filter(username=username).first()

    if user and user.check_password(password):
        logger.info(f"Account [{username}] has enter the network") 
        return Response({"message": "Login successful", "username": user.username}, status=status.HTTP_200_OK)
    else:
        return Response({"error": "Invalid username or password"}, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['POST'])
def logout_user(request):
    username = request.data.get("username")

    if not username:
        return Response({"error": "Username is required"}, status=status.HTTP_400_BAD_REQUEST)

    # Get the user
    user = CustomUser.objects.filter(username=username).first()
    if not user:
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    # Delete the peer associated with the user
    logger.info(f"Account [{username}] has left the swarm") 
    try:
        peer = user.peer  # This gets the peer associated with the user
        peer.delete()  # Deletes the peer model
        logger.info(f"Account [{username}] has left the network") 
        return Response({"message": "User logged out and files removed successfully"}, status=status.HTTP_200_OK)
    except Peer.DoesNotExist:
        return Response({"message": "User logged out and user have no file to remove"}, status=status.HTTP_200_OK)

@api_view(['POST'])
def add_filenames(request):
    username = request.data.get("username")
    address = request.data.get("address")
    info_hash = request.data.get("info_hash")
    name = request.data.get("name")
    piece_length = request.data.get("piece_length")
    filenames = request.data.get("filenames")
    node_id = request.data.get("node_id")


    if not all([username, address, name, info_hash, piece_length, filenames]):
        return Response({"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)

    
    # Get the user
    user = CustomUser.objects.filter(username=username).first()
    if not user:
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    # Check if a peer exists for the user, if not, create one
    peer, created = Peer.objects.get_or_create(user=user, address=address, node_id=node_id)
    peer.add_torrent(info_hash)
    
    # add torrent information
    try:
        torrent = Torrent.objects.create(
            peer=peer,  # Associate the torrent with the peer
            name = name,
            info_hash=info_hash, 
            piece_length = piece_length,
            filenames = filenames
        )
            
    except Exception as e:
        return Response({"error": f"Failed to add torrent: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    logger.info(f"Account [{username}] has published", info_hash) 
    return Response({"message": "Torrent added successfully", "filenames": peer.get_torrents()}, status=status.HTTP_200_OK)

@api_view(['POST'])
def update_freq(request):
    username = request.data.get('username')

    if not username:
        return Response({"error": "Username are required"}, status=status.HTTP_400_BAD_REQUEST)

    user = CustomUser.objects.filter(username=username).first()

    user.update_freq()
    logger.info(f"{username}'s upload frequency got increased by one, [{user.freq}]")





