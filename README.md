# discord-cloud
Absolutely! Here’s a concise overview of what your code does:

### Overview of the Discord Bot and Flask Web Application

1. **Setup**: The application initializes a Discord bot using `discord.py` and a web server using Flask. It loads configuration details (like the Discord token) from a `.env` file.

2. **File Upload**: The web application provides a form for users to upload files. When a file is uploaded:
   - If it’s a ZIP file larger than 8 MB, it is split into smaller parts.
   - For smaller files, it is sent directly to a specified Discord channel.

3. **Sending to Discord**:
   - The bot uploads the files to Discord, generating a unique code for each upload.
   - Metadata about the uploads (like file size, upload time, and download links) is saved in a JSON file.

4. **File Download**: Users can request to download the parts of a large ZIP file using the unique code:
   - The server reconstructs the ZIP file from its parts and sends it to the user.
   - After the download, the combined file is deleted from the server to save space.

5. **Threading**: The bot and the Flask application run concurrently, allowing the web app to handle requests while the bot remains responsive.

This setup creates a seamless experience for uploading large files to Discord while maintaining metadata and facilitating easy downloads. If you need anything specific or further details, let me know!
