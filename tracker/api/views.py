from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth import get_user_model
import json
from .models import CustomUser, Peer
import logging 

#now we will Create and configure logger 
logging.basicConfig(filename='tracker.log',
                    filemode='a',
                    format='%(asctime)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.INFO)


logger = logging.getLogger()

User = get_user_model()

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
    filenames = request.data.get("filenames")  # A list of filenames to be added

    if not username or not filenames:
        return Response({"error": "Username and filenames are required"}, status=status.HTTP_400_BAD_REQUEST)

    # Get the user
    user = CustomUser.objects.filter(username=username).first()
    if not user:
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    # Check if a peer exists for the user, if not, create one
    peer, created = Peer.objects.get_or_create(user=user, address=address)

    # Add filenames to the peer
    peer.add_filename(filenames)
    logger.info(f"Account [{username}] has published [{filenames}]") 
    return Response({"message": "Filenames added successfully", "filenames": peer.get_filenames()}, status=status.HTTP_200_OK)


@api_view(['POST'])
def get_peer_list(request):
    file = request.data.get('filename')

    peers = Peer.objects.all()
    peers_address = []

    for peer in peers:
        if file in peer.filenames:
            peers_address.append(peer.address)
    
    if not peers_address:
        return Response({"peers": "No peers found"}, status=status.HTTP_200_OK)
    return Response({"peers": peers_address}, status=status.HTTP_200_OK)

@api_view(['POST'])
def update_freq(request):
    username = request.data.get('username')

    if not username:
        return Response({"error": "Username are required"}, status=status.HTTP_400_BAD_REQUEST)

    user = CustomUser.objects.filter(username=username).first()

    peer = Peer.objects.get(user=user)
    peer.update_freq()
