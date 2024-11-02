from django.shortcuts import render,redirect
from django.contrib import messages
from django.contrib.auth import authenticate,login
from django.contrib.auth.models import User
from django.contrib.auth import logout
from .forms import JoinQueueForm
from Queueasy.settings import redis_instance  # Import the Redis instance
import json  
from datetime import datetime 
from datetime import timedelta
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .tasks import change_status_to_opened, change_status_to_missed
from .qrcode_generator import generate_qr_code
from django.contrib.auth.decorators import login_required
import logging
import os
from django.http import HttpResponse
from django.http import JsonResponse
import base64
from django.utils import timezone


logger = logging.getLogger(__name__)
#-----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def login_view(request):
    if request.method=='POST':
        username=request.POST['username']
        password=request.POST['password']
        user=authenticate(request, username=username, password=password)
        if user is not None:
            login(request,user)
            messages.success(request,'Login Successful.')
            return redirect('home')
        else:
            messages.error(request,'username or password is incorrect')
    else:
        return render(request,'main/login.html')  
#-----------------------------------------------------------------------------------------------------------------------------------------------------------------------    
def logout_view(request):
    logout(request)
    return redirect('home')
#-----------------------------------------------------------------------------------------------------------------------------------------------------------------------
def register(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        password_confirm = request.POST['password_confirm']
        email = request.POST['email']  # Get the email from the form

        if password == password_confirm:
            if User.objects.filter(username=username).exists():
                messages.error(request, 'Username already exists.')
            elif User.objects.filter(email=email).exists():  # Check if email already exists
                messages.error(request, 'Email already exists.')
            else:
                user = User.objects.create_user(username=username, password=password, email=email)
                user.save()
                messages.success(request, 'Registration successful.')
                login(request, user)
                return redirect('home')
        else:
            messages.error(request, 'Passwords do not match.')
    else:
        # Return the registration form template when it's a GET request
        return render(request, 'main/register.html')
#-----------------------------------------------------------------------------------------------------------------------------------------------------------------------    
def is_user_in_queue(user_id):
    queue = redis_instance.lrange('queue', 0, -1)
    for item in queue:
        user_data = json.loads(item)
        if user_data['user_id'] == user_id:
            return True
    return False
@login_required(login_url='login') 
def join_queue(request):
    if request.method == 'POST':        
        form = JoinQueueForm(request.POST)
        if form.is_valid():
            # Get the form data
            name = request.user.username  
            email = request.user.email 
            number_of_people = form.cleaned_data['number_of_people']            
            # Create a unique user ID
            user_id = f"{email}"
            # Check if the user is already in the queue
            if is_user_in_queue(user_id):
                logger.info(f"User {name} ({user_id}) is already in the queue.")
                return render(request, 'main/already_in_queue.html', {'username': name})                      
            timestamp = datetime.now().isoformat()
            # Calculate the user's position in the queue
            queue_length = redis_instance.llen('queue')
            people_ahead = queue_length  # Current user is not yet in the queue

            # Calculate time slot start and end based on average time per person
            time_slot_start = datetime.now() + timedelta(minutes=(people_ahead) * 2, seconds=10)
            time_slot_end = time_slot_start + timedelta(minutes=2) 
            time_slot_start_str = time_slot_start.strftime("%H:%M")
            time_slot_end_str = time_slot_end.strftime("%H:%M")
            logger.info(f"User {name} ({user_id}) joined the queue at {timestamp}.")
            logger.info(f"Time slot assigned: {time_slot_start_str} - {time_slot_end_str}.")
            qr_code_path = generate_qr_code(user_id, f"{time_slot_start_str} - {time_slot_end_str}", number_of_people)
            with open(qr_code_path, "rb") as qr_file:
                qr_code_base64 = base64.b64encode(qr_file.read()).decode('utf-8')
            qr_code_url = os.path.join('qr_codes', os.path.basename(qr_code_path))           
            change_time_slot_start = (time_slot_start - datetime.now()).total_seconds()
            change_time_slot_end = (time_slot_end - datetime.now()).total_seconds()
            # Only schedule if the times are in the future
            if change_time_slot_start <= 0:
            # Trigger the status change immediately if the time slot has started
                user_data['status'] = 'opened'
                redis_instance.hset(user_id, mapping=user_data)  # Update status in Redis
            else:
                change_status_to_opened.apply_async(args=[user_id], countdown=change_time_slot_start)           
            if change_time_slot_end > 0:
                change_status_to_missed.apply_async(args=[user_id], countdown=change_time_slot_end)
            else:
                logger.warning(f"Cannot schedule status update to missed for {user_id} because the time slot end has already passed.")
           # Create a dictionary to store in Redis
            user_data = {
                'user_id': user_id,
                'name': name,
                'email': email,
                'number_of_people': number_of_people,
                'status': 'waiting',  # Initialize status
                'timestamp': timestamp,  # Store current timestamp
                'time_slot_start': time_slot_start.isoformat(),  # Store start time slot
                'time_slot_end': time_slot_end.isoformat(),  # Store end time slot
                'people_ahead': people_ahead,  # Store the number of people ahead
                'qr_code': qr_code_base64  # Store the QR code as base64 string
            }
            # Add the user data to the Redis queue
            redis_instance.lpush('queue', json.dumps(user_data))
            # Store all user information in a hash using a single hset command
            redis_instance.hset(user_id, mapping=user_data)
            logger.info(f"User {name} ({user_id}) joined the queue at {timestamp}.")
            logger.info(f"Time slot assigned: {time_slot_start_str} - {time_slot_end_str}.")
            logger.info(f"User data inserted into Redis: {user_data}")
            # Redirect to the joined queue page
            return render(request, 'main/joined_queue.html', {
                'user_id': user_id,
                'email': email,
                'number_of_people': number_of_people,
                'timestamp': timestamp,
                'time_slot': f"{time_slot_start_str} - {time_slot_end_str}", 
                'qr_code_path': qr_code_url
            })
    else:
        form = JoinQueueForm()
    return render(request, 'main/join_queue.html', {'form': form})
def home(request):
    return render(request,'main/home.html')
#-----------------------------------------------------------------------------------------------------------------------------------------------------------------------    
@login_required(login_url='login')
def check_status(request):
    # Retrieve the logged-in user's email from the session
    user_email = request.user.email  # Assuming the user's email is stored in the session
    
    # Fetch all user IDs currently in the 'queue' key
    queue_members = redis_instance.lrange('queue', 0, -1)

# Check if the user's email is present in any of the JSON entries in the queue
    user_in_queue = False
    user_data = None

    for member in queue_members:
        # Decode each member and parse the JSON data
        member_data = json.loads(member.decode('utf-8'))
        if member_data.get("user_id") == user_email:
            user_in_queue = True
            user_data = member_data
            break

    if not user_in_queue:
        # User is not in the queue
        queue_length = len(queue_members)
        return render(request, 'main/check_status.html', {
            'message': f"Sorry! {request.user.username}, you are not in the queue currently.",
            'queue_length': queue_length
        })
    # User is in the queue, decode and prepare the user data
  
    joined_timestamp = user_data.get('timestamp')
    user_id = user_data.get('user_id')
    number_of_people = user_data.get('number_of_people')
    time_slot_start = timezone.make_aware(datetime.fromisoformat(user_data.get('time_slot_start')))
    time_slot_end = timezone.make_aware(datetime.fromisoformat(user_data.get('time_slot_end')))
    status = user_data.get('status')
    people_ahead = user_data.get('people_ahead')
    qr_code_base64 = user_data.get('qr_code')

    # Calculate remaining time till slot opens
    current_time = timezone.now()  

    remaining_time_seconds = max(0, (time_slot_start - current_time).total_seconds())
    # Calculate remaining time till slot closes
    remaining_time_seconds_close = max(0, (time_slot_end - current_time).total_seconds())

    # Decode QR code for display
    qr_code_url = f"data:image/png;base64,{qr_code_base64}"

    return render(request, 'main/check_status.html', {
        'joined_timestamp': joined_timestamp,
        'user_id': user_id,
        'number_of_people': number_of_people,
        'time_slot_start': time_slot_start.strftime("%H:%M:%S"),
        'time_slot_end': time_slot_end.strftime("%H:%M:%S"),
        'time_slot_start_r': time_slot_start.isoformat(),  # Pass ISO format
    'time_slot_end_r': time_slot_end.isoformat(), 
        'status': status,
        'remaining_time_seconds': remaining_time_seconds,
        'remaining_time_seconds_close':remaining_time_seconds_close,
        'people_ahead': people_ahead,
        'qr_code_url': qr_code_url
    })
#-----------------------------------------------------------------------------------------------------------------------------------------------------------------------    
@login_required(login_url='login')
def get_realtime_data(request):
    user_email = request.user.email
    user_data = redis_instance.hgetall(user_email)

    if not user_data:
        return JsonResponse({'error': 'User not in queue'}, status=404)

    user_data = {k.decode('utf-8'): v.decode('utf-8') for k, v in user_data.items()}
    status = user_data.get('status')
    
    #print(f"Fetched data for {user_email}: status={status}, people_ahead={people_ahead}")  # Log for debugging
    
    
    
    
    
    
    queue_members = redis_instance.lrange('queue', 0, -1)
    user_data_queue = None
    user_in_queue = False
    people_ahead = 0
    for member in queue_members:
        # Decode each member and parse the JSON data
        member_data = json.loads(member.decode('utf-8'))
        if member_data.get("user_id") == user_email:
            user_in_queue = True
            user_data_queue = member_data
            break
    if not user_in_queue:
        user_data_queue = None
    if user_in_queue:
        people_ahead = int(user_data_queue.get('people_ahead'))  # Ensure it's treated as an integer
    return JsonResponse({
        'status': status,
        'people_ahead': people_ahead
    })
#------------------------------------------------------------------------------------------------------------------------------
def download_qr_code(request):
    # Retrieve the QR code data from Redis (or wherever you have it stored)
    user_email = request.user.email
    qr_code_base64 = redis_instance.hget(user_email, 'qr_code')

    if qr_code_base64:
        qr_code_bytes = base64.b64decode(qr_code_base64)
        response = HttpResponse(qr_code_bytes, content_type='image/png')
        response['Content-Disposition'] = 'attachment; filename="qr_code.png"'
        return response

    return HttpResponse("QR code not found.", status=404)
#--------------------------------------------------------------------------------------------------------------------------------------------------------
@login_required
def history(request):
    entries = []
    status = request.GET.get('status', 'missed')  # Default to missed entries

    if status == 'missed':
        # Retrieve data from missed_slots in Redis
        missed_slots = redis_instance.lrange('missed_slots', 0, -1)
        for entry in missed_slots:
            decoded_entry = entry.decode('utf-8')  # Decode the bytes to a string
            try:
                # Parse the JSON string into a Python dictionary
                entry_data = json.loads(decoded_entry)

                # Extract relevant fields
                timestamp = datetime.fromisoformat(entry_data['timestamp'])
                num_people = entry_data.get('number_of_people')
                
                time_slot_start = datetime.fromisoformat(entry_data['time_slot_start'])
                time_slot_end = datetime.fromisoformat(entry_data['time_slot_end'])

                # Format timestamp and time slots
                date_time = timestamp.strftime("%d/%m/%Y %H:%M")
                time_slot = f"{time_slot_start.strftime('%H:%M')} - {time_slot_end.strftime('%H:%M')}"

                entries.append({
                    'date_time': date_time,
                    'num_people': num_people,  # Adjust this based on your logic for number of people
                    'time_slot': time_slot,
                    'status': 'Missed'
                })
            except (ValueError, KeyError) as e:
                print(f"Error processing entry: {decoded_entry} - {e}")

    return render(request, 'main/history.html', {'entries': entries, 'selected_status': status})
'''    elif status == 'entered':
        # Retrieve data from missed_slots in Redis
        missed_slots = redis_instance.lrange('entered_slots', 0, -1)
        for entry in missed_slots:
            decoded_entry = entry.decode('utf-8')  # Decode the bytes to a string
            try:
                # Parse the JSON string into a Python dictionary
                entry_data = json.loads(decoded_entry)

                # Extract relevant fields
                date_time = entry_data['timestamp']
                num_people = 1  # Adjust this based on your logic for number of people
                time_slot = f"{entry_data['time_slot_start']} - {entry_data['time_slot_end']}"
                entries.append({
                    'date_time': date_time,
                    'num_people': num_people,
                    'time_slot': time_slot,
                    'status': 'Missed'
                })
            except (ValueError, KeyError) as e:
                print(f"Error processing entry: {decoded_entry} - {e}")

    elif status == 'canceled':
        # Retrieve data from missed_slots in Redis
        missed_slots = redis_instance.lrange('canceled_slots', 0, -1)
        for entry in missed_slots:
            decoded_entry = entry.decode('utf-8')  # Decode the bytes to a string
            try:
                # Parse the JSON string into a Python dictionary
                entry_data = json.loads(decoded_entry)

                # Extract relevant fields
                date_time = entry_data['timestamp']
                num_people = 1  # Adjust this based on your logic for number of people
                time_slot = f"{entry_data['time_slot_start']} - {entry_data['time_slot_end']}"
                entries.append({
                    'date_time': date_time,
                    'num_people': num_people,
                    'time_slot': time_slot,
                    'status': 'Missed'
                })
            except (ValueError, KeyError) as e:
                print(f"Error processing entry: {decoded_entry} - {e}")'''

    

  






