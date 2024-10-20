import os
import io
import discord
from discord import File
import random
import string
import json
import hashlib
from datetime import datetime
from flask import Flask, request, render_template, jsonify, send_file
import threading
import asyncio
import requests
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Discord bot setup
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = CHANNEL_ID

intents = discord.Intents.default()
intents.messages = True
client = discord.Client(intents=intents)

# Flask app setup
app = Flask(__name__)

# Max part size for splitting large files
PART_SIZE = 8 * 1024 * 1024  # 8 MB
zip_mapping = {}

# Wait until the bot is ready and fetch the channel
channel = None

@client.event
async def on_ready():
    global channel
    channel = client.get_channel(CHANNEL_ID)
    print(f'{client.user} has connected to Discord!')

@app.route('/')
def index():
    """Render the homepage with the file upload form."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file uploads and send them to Discord."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    file_path = os.path.join('uploads', file.filename)
    file.save(file_path)  # Save the file locally

    if file_path.endswith('.zip') and os.path.getsize(file_path) > PART_SIZE:
        unique_code = asyncio.run_coroutine_threadsafe(send_large_zip(file_path), client.loop).result()
        return jsonify({'message': 'File uploaded and will be processed', 'unique_code': unique_code}), 200
    else:
        asyncio.run_coroutine_threadsafe(send_single_file(file_path), client.loop)
        return jsonify({'message': 'File uploaded successfully'}), 200

async def send_single_file(file_path):
    """Send a single file to Discord."""
    await client.wait_until_ready()

    if channel is None:
        print("Channel not found. Ensure the bot has connected and the correct channel ID is used.")
        return

    file_checksum = calculate_checksum(file_path)
    with open(file_path, 'rb') as f:
        msg = await channel.send(file=File(f, os.path.basename(file_path)))

        # Generate a unique code for the file
        unique_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        metadata = {
            "file_name": os.path.basename(file_path),
            "file_size": os.path.getsize(file_path),
            "file_type": os.path.splitext(file_path)[1],
            "discord_link": msg.attachments[0].url,
            "unique_code": unique_code,
            "channel_id": CHANNEL_ID,
            "upload_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "file_checksum": file_checksum,
            "download_count": 0
        }

        # Create a folder with the format 'filename_unique_code'
        folder_name = os.path.join('uploads', f"{os.path.splitext(os.path.basename(file_path))[0]}_{unique_code}")
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)

        metadata_filename = os.path.join(folder_name, "metadata.json")
        with open(metadata_filename, 'w') as meta_file:
            json.dump(metadata, meta_file, indent=4)

    os.remove(file_path)

async def send_large_zip(file_path):
    """Split a large zip file and send parts to Discord."""
    part_number = 1
    unique_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    zip_mapping[unique_code] = []

    total_size = os.path.getsize(file_path)
    file_checksum = calculate_checksum(file_path)

    await client.wait_until_ready()

    if channel is None:
        print("Channel not found. Ensure the bot has connected and the correct channel ID is used.")
        return

    with open(file_path, 'rb') as f:
        while True:
            part_data = f.read(PART_SIZE)
            if not part_data:
                break

            part_filename = f"{os.path.splitext(os.path.basename(file_path))[0]}_part{part_number}.zip"
            part_file = discord.File(io.BytesIO(part_data), part_filename)
            
            msg = await channel.send(file=part_file)
            zip_mapping[unique_code].append(msg.attachments[0].url)

            part_number += 1

    os.remove(file_path)

    # Create a folder with the format 'filename_unique_code'
    folder_name = os.path.join('uploads', f"{os.path.splitext(os.path.basename(file_path))[0]}_{unique_code}")
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

    metadata = {
        "file_name": os.path.basename(file_path),
        "file_size": total_size,
        "file_type": os.path.splitext(file_path)[1],
        "discord_links": zip_mapping[unique_code],
        "unique_code": unique_code,
        "channel_id": CHANNEL_ID,
        "upload_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "file_checksum": file_checksum,
        "num_parts": part_number - 1,
        "download_count": 0
    }

    metadata_filename = os.path.join(folder_name, "metadata.json")
    with open(metadata_filename, 'w') as meta_file:
        json.dump(metadata, meta_file, indent=4)

    return unique_code

@app.route('/download', methods=['POST'])
def download_file():
    """Download the parts of the file using the unique code."""
    unique_code = request.form.get('unique_code')
    if unique_code not in zip_mapping:
        return jsonify({'error': 'Invalid unique code'}), 400

    combined_filename = os.path.join('uploads', f'combined_{unique_code}.zip')
    try:
        with open(combined_filename, 'wb') as combined_file:
            for link in zip_mapping[unique_code]:
                # Download each part and write to the combined file
                response = requests.get(link)
                combined_file.write(response.content)

        # Send the combined file to the client
        response = send_file(combined_filename, as_attachment=True)

        # Start a thread to delete the file after download
        def delete_combined_file(filename):
            time.sleep(10)  # Wait for 10 seconds to ensure download completes
            try:
                os.remove(filename)
                print(f"Deleted {filename} successfully.")
            except PermissionError:
                print(f"Could not delete {filename}. It might be in use.")

        threading.Thread(target=delete_combined_file, args=(combined_filename,), daemon=True).start()

        return response

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def calculate_checksum(file_path):
    """Calculate the SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

# Run the bot and the website together
def run_bot():
    client.run(TOKEN)

if __name__ == '__main__':
    if not os.path.exists('uploads'):
        os.makedirs('uploads')  # Ensure the uploads folder exists

    # Start the Discord bot in a new thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    # Run the Flask app without auto-reloading
    app.run(debug=False, use_reloader=False, port=5000)
