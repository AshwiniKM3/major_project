from django.conf import settings
import os
import qrcode
import json

def generate_qr_code(user_id, time_slot, number_of_people, file_name=None):
    # Create a unique file name if not provided
    if not file_name:
        file_name = f"qrcode_{user_id}.png"

    # Information to encode
    data = {
        'user_id': user_id,
        'time_slot': time_slot,
        'number_of_people': number_of_people
    }
    data_string = json.dumps(data)

    # Generate the QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data_string)
    qr.make(fit=True)

    # Create an image from the QR code
    img = qr.make_image(fill='black', back_color='white')

    # Use an absolute path for saving the QR code image
    qr_code_dir = os.path.join(settings.BASE_DIR, 'static', 'qr_codes')
    
    # Make sure the directory exists
    os.makedirs(qr_code_dir, exist_ok=True)
    
    qr_code_path = os.path.join(qr_code_dir, file_name)
    img.save(qr_code_path)
    return qr_code_path

